"""Reglas de traslados sin base de datos ni Flask: documentos y líneas son objetos simples."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from dominio import traslados as dom
from dominio.errores import Conflicto, ErrorDominio, NoEncontrado, Prohibido

ANALISTA, GERENTE = ('Ana', 'analista'), ('Carlos', 'gerente')


class Registro(SimpleNamespace):
    __hash__ = object.__hash__  # como los modelos ORM: hashable por identidad


def linea(id_, sugerida, nombre='Aceite', **extra):
    return Registro(id=id_, articulo_codigo=f'C{id_}', articulo_nombre=nombre, clasificacion_abc='A',
                           origen=dom.ALMACEN, destino='Barcelona', estado='borrador', cantidad_sugerida=sugerida,
                           cantidad_aprobada=None, cantidad_despachada=None, cantidad_recibida=None,
                           cobertura_dias=1.0, retirado_en=None, actualizado_en=datetime(2026, 1, 1), **extra)


def documento(*lineas, estado='borrador'):
    d = Registro(id=7, estado=estado, lineas=list(lineas), motivo_rechazo=None, observaciones=None, version=1,
                        actualizado_en=datetime(2026, 1, 1))
    dom.fijar_estado(d, estado)
    return d


def sobra(_linea):
    return 1000, 0


def test_ciclo_completo_con_diferencias():
    d = documento(linea(1, 10), linea(2, 5, 'Jabón'))
    dom.aplicar_accion(d, 'enviar', {}, ANALISTA, sobra)
    e = dom.aplicar_accion(d, 'aprobar', {'cantidades': {'1': 8}}, GERENTE, sobra)
    assert e['detalle']['despues'] == {'unidades_aprobadas': 13}
    assert [l.cantidad_aprobada for l in d.lineas] == [8, 5]
    dom.aplicar_accion(d, 'despachar', {}, ANALISTA, sobra)
    with pytest.raises(ErrorDominio, match='describe la diferencia'):
        dom.aplicar_accion(d, 'recibir', {'cantidades': {'1': 7, '2': 5}}, ANALISTA, sobra)
    e = dom.aplicar_accion(d, 'recibir', {'cantidades': {'1': 7, '2': 5}, 'comentario': 'Llegó una rota'}, ANALISTA, sobra)
    assert d.estado == 'recibido_con_diferencias' and e['tipo'] == 'recibido_con_diferencias'
    assert e['detalle']['articulos'][0]['despues'] == {'cantidad_recibida': 7, 'diferencia': -1}
    assert dom.diferencia_de(d.lineas[0]) == -1
    with pytest.raises(ErrorDominio, match='concilió'):
        dom.aplicar_accion(d, 'cerrar', {}, GERENTE, sobra)
    dom.aplicar_accion(d, 'cerrar', {'comentario': 'Ajuste de inventario'}, GERENTE, sobra)
    assert d.estado == 'cerrado' and all(l.estado == 'cerrado' for l in d.lineas)
    assert d.version == 6  # 5 acciones aplicadas; las rechazadas no suben la versión


def test_transicion_invalida_y_rol():
    d = documento(linea(1, 10))
    with pytest.raises(Conflicto):
        dom.aplicar_accion(d, 'despachar', {}, ANALISTA, sobra)
    dom.aplicar_accion(d, 'enviar', {}, ANALISTA, sobra)
    with pytest.raises(Prohibido):
        dom.aplicar_accion(d, 'aprobar', {}, ANALISTA, sobra)
    assert dom.acciones_disponibles(d, 'analista') == []
    assert dom.acciones_disponibles(d, 'gerente') == ['aprobar', 'rechazar']


def test_no_se_reserva_mas_que_lo_disponible():
    d = documento(linea(1, 30))
    with pytest.raises(ErrorDominio, match='tiene 20 unidades disponibles'):
        dom.aplicar_accion(d, 'enviar', {}, ANALISTA, lambda l: (50, 30))
    assert d.estado == 'borrador'


def test_reservado_cuenta_solo_estados_que_comprometen_y_excluye_la_propia_linea():
    abiertas = [linea(1, 10), linea(2, 4), linea(3, 6)]
    abiertas[0].estado = 'pendiente_aprobacion'
    abiertas[1].estado = 'aprobado'
    abiertas[1].cantidad_aprobada = 3
    abiertas[2].estado = 'despachado'  # ya salió: no se descuenta
    assert dom.reservado(abiertas) == 13
    assert dom.reservado(abiertas, excluir_id=1) == 3


def test_verificar_version():
    d = documento(linea(1, 10))
    with pytest.raises(ErrorDominio, match='Falta la versión'):
        dom.verificar_version(d, {})
    with pytest.raises(Conflicto):
        dom.verificar_version(d, {'version': 2})
    dom.verificar_version(d, {'version': '1'})


def test_editar_solo_en_borrador_y_sin_cambios_no_genera_eventos():
    d = documento(linea(1, 10))
    assert dom.editar(d, {'lineas': [{'id': 1, 'cantidad_sugerida': 10}]}, ANALISTA, sobra) == []
    assert d.version == 1
    eventos = dom.editar(d, {'lineas': [{'id': 1, 'cantidad_sugerida': 12}], 'observaciones': 'Urgente'}, ANALISTA, sobra)
    assert [e['tipo'] for e in eventos] == ['cantidad_modificada', 'observaciones']
    assert d.lineas[0].cantidad_sugerida == 12 and d.version == 2
    dom.aplicar_accion(d, 'enviar', {}, ANALISTA, sobra)
    with pytest.raises(Conflicto):
        dom.editar(d, {'lineas': [{'id': 1, 'cantidad_sugerida': 5}]}, ANALISTA, sobra)


def test_retirar_linea():
    d = documento(linea(1, 10), linea(2, 5))
    with pytest.raises(NoEncontrado):
        dom.retirar_linea(d, 99, {}, ANALISTA)
    dom.retirar_linea(d, 2, {}, ANALISTA)
    assert [l.id for l in dom.lineas_vigentes(d)] == [1] and d.lineas[1].estado == 'descartado'
    with pytest.raises(ErrorDominio, match='único artículo'):
        dom.retirar_linea(d, 1, {}, ANALISTA)


def test_en_aprobacion_solo_el_gerente_retira():
    d = documento(linea(1, 10), linea(2, 5), estado='pendiente_aprobacion')
    with pytest.raises(Conflicto):
        dom.retirar_linea(d, 2, {}, ANALISTA)
    dom.retirar_linea(d, 2, {}, GERENTE)


def test_propuestas_omiten_rutas_con_traslado_abierto_y_filtran_clases():
    sugerencias = [{'codigo': 'C1', 'sucursal': 'Barcelona', 'clasificacion_abc': 'A'},
                   {'codigo': 'C2', 'sucursal': 'Barcelona', 'clasificacion_abc': 'A'},
                   {'codigo': 'C3', 'sucursal': 'Maturín', 'clasificacion_abc': 'C'}]
    abiertas = [linea(1, 10)]  # C1: almacén -> Barcelona
    por_destino, total = dom.propuestas_por_destino(sugerencias, abiertas, ['A'])
    assert total == 2 and [s['codigo'] for s in por_destino['Barcelona']] == ['C2'] and 'Maturín' not in por_destino


def test_comprometido_en_almacen():
    aprobada = linea(1, 10)
    aprobada.estado, aprobada.cantidad_aprobada = 'aprobado', 8
    borrador = linea(2, 5)
    assert dom.comprometido_en_almacen([aprobada, borrador]) == {'C1': 8}
