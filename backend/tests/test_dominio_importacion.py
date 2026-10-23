"""Interpretación de filas de reportes sin pandas ni base de datos."""
from datetime import date

import pytest

from dominio import importacion as dom
from dominio.errores import ErrorDominio


def fila_venta(**extra):
    return {'codigo': 'A1', 'nombre': 'Aceite', 'emision': '2026-10-05', 'cantidad': 3, 'cntdevuelt': 1,
            'preciofin': 100, 'factor': 40, 'costoex': 2, 'nombredegr': 'viveres', 'nombrecli': 'CLIENTE', **extra}


def test_ventas_calculan_factura_en_bs_costo_con_iva_y_tasa_bcv():
    ventas, tasas, conteos = dom.ventas_desde_filas([fila_venta()], 'Barcelona')
    v = ventas[0]
    assert v['cantidad_neta'] == 2 and v['factura_bs'] == pytest.approx(232) and v['factura_real_usd'] == pytest.approx(5.8)
    assert v['costo_real_usd'] == pytest.approx(4.64) and v['grupo_venta'] == 'VIVERES' and v['sucursal'] == 'Barcelona'
    assert tasas == {date(2026, 10, 5): 40} and conteos == {'internas': 0, 'sin_fecha': 0, 'por_excepcion': {}}


def test_ventas_con_columna_fact_y_filas_descartadas():
    filas = [fila_venta(fact=9, factor=None), fila_venta(codigo=None), fila_venta(nombredegr='MARKETING'),
             fila_venta(emision='mañana'), fila_venta(nombrecli='BROTCARS', factor=0.5)]
    ventas, tasas, conteos = dom.ventas_desde_filas(filas, 'Barcelona')
    assert [v['factura_bs'] for v in ventas] == [None, None] and ventas[0]['factura_real_usd'] == 9
    assert ventas[1]['excepcion'] == 'brotcars' and ventas[1]['factor_sistema'] == 0.5 and tasas == {}
    assert conteos == {'internas': 1, 'sin_fecha': 1, 'por_excepcion': {'brotcars': 1}}
    assert 'Brotcars: 1' in dom.mensaje_ventas('Barcelona', ventas, tasas, conteos)


def test_inventario_cuenta_repetidos_como_actualizacion_y_limpia_internos():
    filas = [{'codigo': 12345.0, 'nombre': 'Tornillo', 'existencia': 5, 'costoex': 1, 'nombredegr': None},
             {'codigo': '12345', 'nombre': 'otro', 'existencia': 7, 'costoex': 2, 'nombredegr': 'ferreteria'},
             {'codigo': 'B1', 'existencia': 1, 'costoex': 3, 'nombredegr': None, 'precio1': 9},
             {'codigo': 'M1', 'existencia': 1, 'nombredegr': 'MARKETING'}]
    articulos, existencias, internos, conteos = dom.inventario_desde_filas(filas, 'INVAL', {'B1': 'VARIOS', 'V': 'marketing'})
    assert articulos['12345'] == {'nuevo': True, 'nombre': 'Tornillo', 'grupo': 'FERRETERIA', 'costo': 2}
    assert articulos['B1'] == {'nuevo': False, 'grupo': None, 'costo': 3}
    assert existencias == {'12345': (7, None), 'B1': (1, 9)}  # el almacén toma el precio de PRECIO1
    assert internos == {'M1', 'V'} and conteos == {'nuevos': 1, 'actualizados': 2}


def test_precio_de_sucursal_solo_de_precio1ex():
    assert dom.precio_venta_usd({'precio1': 900}, 'INV') is None
    assert dom.precio_venta_usd({'precio1ex': '2,12345'}, 'INV') == 2.1235


def test_tasas_sin_filas_validas():
    assert dom.tasas_desde_filas([{'fecha': '01/10/2026', 'tasa': 40}, {'fecha': None, 'tasa': 1}]) == {date(2026, 10, 1): 40}
    with pytest.raises(ErrorDominio):
        dom.tasas_desde_filas([{'fecha': '01/10/2026', 'tasa': 0}])


def test_canonizar_sucursal():
    assert dom.canonizar_sucursal('  MATURIN ', {'Maturín', 'Barcelona'}) == 'Maturín'
    assert dom.canonizar_sucursal('puerto  la cruz', set()) == 'Puerto La Cruz'
    assert dom.canonizar_sucursal(None, {'Maturín'}) == ''
