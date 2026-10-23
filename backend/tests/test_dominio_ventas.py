"""Reglas de ventas y tasas sin base de datos."""
from datetime import date

import pytest

from dominio import ventas as dom
from dominio.comun import numero, parsear_fecha
from dominio.errores import ErrorDominio


def test_excepciones_por_defecto_y_guardadas():
    por_defecto = dom.excepciones_configuradas({})
    assert 'reposicion_maturin' in por_defecto and 'mercancia_extraviada' not in por_defecto
    guardadas = dom.excepciones_configuradas({'reposicion_maturin': False, 'mercancia_extraviada': True})
    assert 'reposicion_maturin' not in guardadas and 'mercancia_extraviada' in guardadas


def test_excluir_de_parametro_ignora_ids_desconocidos():
    assert dom.excluir_de_parametro('brotcars,xx') == ['brotcars']
    assert dom.excluir_de_parametro('') == []


def test_validar_seleccion():
    seleccion = dom.validar_seleccion(['brotcars'])
    assert seleccion['brotcars'] is True and set(seleccion) == dom.IDS_EXCEPCION and sum(seleccion.values()) == 1
    for invalida in (['nope'], 'brotcars', None):
        with pytest.raises(ErrorDominio):
            dom.validar_seleccion(invalida)


def test_rentabilidad_sin_ventas_no_tiene_margen():
    assert dom.rentabilidad('G', 0, 5, 0)['margen'] is None
    assert dom.rentabilidad('G', 200, 150, 10) == {'grupo': 'G', 'total': 200, 'costo': 150, 'utilidad': 50,
                                                   'margen': 25.0, 'ventas_sin_costo': 10}


def test_analisis_agrupa_en_otros_fuera_de_los_principales():
    filas = [('Barcelona', f'G{i}', 100 - i * 10, 10, 0) for i in range(7)] + [('Maturín', 'G6', 500, 0, 500)]
    principales, sucursales = dom.analisis_por_sucursal(filas)
    assert principales == ['G6', 'G0', 'G1', 'G2', 'G3']  # G6 suma 540 entre las dos sucursales
    assert [s['sucursal'] for s in sucursales] == ['Maturín', 'Barcelona']  # 500 contra 490
    barcelona = sucursales[1]
    assert [g['grupo'] for g in barcelona['grupos']] == ['G6', 'G0', 'G1', 'G2', 'G3', 'OTROS']
    assert barcelona['grupos'][-1]['total'] == 60 + 50  # G4 y G5
    assert len(barcelona['todos_los_grupos']) == 7 and sucursales[0]['ventas_sin_costo'] == 500


def test_ultimos_dias_rellena_con_cero():
    serie = dom.ultimos_dias(date(2026, 10, 7), {date(2026, 10, 1): 5, date(2026, 10, 7): 2.345})
    assert [d['total'] for d in serie] == [5, 0, 0, 0, 0, 0, 2.35] and serie[0]['fecha'] == '2026-10-01'


def test_leer_lista_tasas():
    assert dom.leer_lista_tasas('2026-10-01 36,50\n02/10/2026\t36.75\nbasura\n2026-10-03 x\n') == [
        (date(2026, 10, 1), 36.5), (date(2026, 10, 2), 36.75)]


def test_numero_y_fecha_toleran_valores_vacios():
    assert numero(float('nan'), 7) == 7 and numero('1,5') == 1.5 and numero(None, None) is None
    assert parsear_fecha(float('nan')) is None and parsear_fecha('15/10/2026 08:00') == date(2026, 10, 15)
