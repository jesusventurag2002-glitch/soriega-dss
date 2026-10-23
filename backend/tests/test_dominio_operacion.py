"""Seguimiento de estancado y piso de venta sin base de datos."""
from types import SimpleNamespace

import pytest

from dominio import estancado, tienda
from dominio.errores import Conflicto, ErrorDominio
from dominio.traslados import ALMACEN

USUARIO = ('Ana', 'gerente')


def test_nueva_accion_valida_articulo_tipo_y_duplicado():
    art = SimpleNamespace(codigo='Z1')
    with pytest.raises(ErrorDominio, match='no existe'):
        estancado.validar_nueva_accion(None, 'promocion', lambda c, t: False)
    with pytest.raises(ErrorDominio, match='inválido'):
        estancado.validar_nueva_accion(art, 'regalo', lambda c, t: False)
    with pytest.raises(Conflicto):
        estancado.validar_nueva_accion(art, 'promocion', lambda c, t: (c, t) == ('Z1', 'promocion'))
    estancado.validar_nueva_accion(art, 'devolucion_proveedor', lambda c, t: (c, t) == ('Z1', 'promocion'))


def test_cerrar_accion():
    accion = SimpleNamespace(estado='pendiente', resultado=None, cerrado_por=None, cerrado_en=None)
    with pytest.raises(ErrorDominio, match='resultado'):
        estancado.cerrar_accion(accion, {'estado': 'completada', 'resultado': 'ok'}, USUARIO)
    with pytest.raises(ErrorDominio, match='Estado inválido'):
        estancado.cerrar_accion(accion, {'estado': 'pendiente'}, USUARIO)
    estancado.cerrar_accion(accion, {'estado': 'descartada'}, USUARIO)
    assert (accion.estado, accion.resultado, accion.cerrado_por) == ('descartada', None, 'Ana')
    with pytest.raises(Conflicto):
        estancado.cerrar_accion(accion, {'estado': 'completada', 'resultado': 'Vendido'}, USUARIO)


def test_existencias_suman_por_ubicacion_con_el_almacen_primero():
    filas = [('A1', 'INV', 'Maturín', 3, None), ('A1', 'INVAL', None, 10, 2.5), ('A1', 'INV', None, 1, 4),
             ('A1', 'INV', 'Barcelona', 2, 4)]
    assert tienda.existencias_por_ubicacion(filas) == {'A1': [
        (ALMACEN, 10, 2.5), ('Barcelona', 2, 4.0), ('Maturín', 3, None), ('Sin asignar', 1, 4.0)]}


def test_conteo_y_revision_de_discrepancias():
    with pytest.raises(ErrorDominio, match='coincide'):
        tienda.validar_conteo(5, 5, 'sobra')
    with pytest.raises(ErrorDominio, match='Describe'):
        tienda.validar_conteo(4, 5, 'x')
    tienda.validar_conteo(4, 5, 'falta una')

    d = SimpleNamespace(estado='pendiente', resolucion=None, revisado_por=None, revisado_en=None)
    with pytest.raises(ErrorDominio):
        tienda.revisar_discrepancia(d, {'resolucion': 'no'}, USUARIO)
    tienda.revisar_discrepancia(d, {'resolucion': 'Ajustado en sistema'}, USUARIO)
    assert (d.estado, d.revisado_por) == ('revisada', 'Ana')
    with pytest.raises(Conflicto):
        tienda.revisar_discrepancia(d, {'resolucion': 'Otra vez'}, USUARIO)


def test_retornos_por_articulo():
    linea = SimpleNamespace(articulo_codigo='Z1', documento_id=4, documento=SimpleNamespace(id=4), origen='Barcelona',
                            estado='borrador', cantidad_recibida=None, cantidad_despachada=None, cantidad_aprobada=None,
                            cantidad_sugerida=3)
    assert estancado.retornos_por_articulo([linea]) == {
        'Z1': [{'id': 4, 'folio': 'TR-00004', 'origen': 'Barcelona', 'estado': 'borrador', 'cantidad': 3}]}
