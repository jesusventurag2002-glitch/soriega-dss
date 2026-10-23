"""Reglas de demanda sin base de datos: los agregados se escriben a mano."""
from datetime import date
from types import SimpleNamespace

from dominio import demanda as dom
from dominio.traslados import ALMACEN


def articulo(codigo, costo=1, nombre=None):
    return SimpleNamespace(codigo=codigo, nombre=nombre or codigo, nombredegrupo='G', proveedor='P', costoex=costo)


def test_clasificacion_abc_por_participacion_acumulada():
    # Total 100; la clase depende de lo acumulado ANTES del artículo: 0% y 70% -> A, 90% -> B, 96% -> C.
    abc = dom.clasificar_abc([('C', 6), ('A', 70), ('D', 4), ('B', 20)])
    assert abc == {'A': 'A', 'B': 'A', 'C': 'B', 'D': 'C'}
    assert dom.clasificar_abc([]) == {}


def test_venta_diaria_usa_el_rango_de_fechas():
    assert dom.venta_diaria(20, date(2026, 10, 1), date(2026, 10, 10)) == 2
    assert dom.venta_diaria(30, None, None) == 1  # sin fechas se asume un mes


def demanda_dos_sucursales():
    """A1: 30 u en el almacén; Barcelona tiene 2 y vende 2/día, Maturín 0 y vende 2/día."""
    return dom.demanda(
        existencias=[('A1', 'INVAL', None, 30), ('A1', 'INV', 'Barcelona', 2), ('A1', 'INV', 'Maturín', 0)],
        ventas_por_sucursal=[('A1', 'Barcelona', 20, date(2026, 10, 1), date(2026, 10, 10)),
                             ('A1', 'Maturín', 20, date(2026, 10, 1), date(2026, 10, 10))],
        ventas_por_articulo=[('A1', 40, date(2026, 10, 1), date(2026, 10, 10))],
    )


def test_sugerencias_atienden_primero_la_menor_cobertura():
    s = dom.sugerencias_traslado([articulo('A1')], demanda_dos_sucursales(), {'A1': 'A'}, dias=15)
    # Maturín (0 días de cobertura) recibe sus 30 y Barcelona se queda sin stock que repartir.
    assert [(x['sucursal'], x['cantidad']) for x in s] == [('Maturín', 30)]


def test_sugerencias_descuentan_lo_comprometido():
    s = dom.sugerencias_traslado([articulo('A1')], demanda_dos_sucursales(), {}, dias=15, comprometido_almacen={'A1': 25})
    assert [(x['sucursal'], x['cantidad'], x['clasificacion_abc']) for x in s] == [('Maturín', 5, 'C')]


def test_reposicion_pide_el_deficit_de_la_red():
    r = dom.reposicion([articulo('A1')], demanda_dos_sucursales(), {'A1': 'A'}, dias=15)
    assert r[0]['cantidad_pedir'] == 4 * 15 - 32


def test_criticos_solo_a_y_b_con_cobertura_baja():
    dem = demanda_dos_sucursales()
    abierta = SimpleNamespace(articulo_codigo='A1', destino='Maturín', documento_id=3,
                              documento=SimpleNamespace(id=3), estado='aprobado')
    items = dom.productos_criticos(dem, {'A1': 'A'}, {'A1': 'Aceite'}, [abierta])
    assert [(i['sucursal'], i['cobertura_dias']) for i in items] == [('Maturín', 0), ('Barcelona', 1)]
    assert items[0]['traslado'] == {'id': 3, 'folio': 'TR-00003', 'estado': 'aprobado'} and items[1]['traslado'] is None
    assert dom.productos_criticos(dem, {'A1': 'C'}, {'A1': 'Aceite'}, []) == []
    assert dom.productos_criticos(dem, {'A1': 'A'}, {'A1': 'Aceite'}, [], sucursal='Barcelona', dias=1) == []


def test_capital_estancado_por_ubicacion():
    existencias = [('A1', 'INVAL', None, 10), ('A1', 'INV', 'Barcelona', 4), ('B1', 'INV', 'Barcelona', 3),
                   ('X', 'INVAL', None, 99)]
    articulos = [articulo('A1', 2), articulo('B1', 1), articulo('X', 0)]  # sin costo no cuenta
    args = (date(2026, 1, 1), date(2026, 6, 30), {'A1': date(2026, 2, 1)}, existencias, articulos)

    consolidado = dom.capital_estancado(*args, dias_min=90)
    assert [(a['codigo'], a['existencia'], a['capital_estancado']) for a in consolidado['articulos']] == [
        ('A1', 14, 28), ('B1', 3, 3)]
    assert consolidado['articulos'][1]['sin_ventas'] and consolidado['articulos'][1]['dias_sin_vender'] == 180
    assert dom.capital_estancado(*args, dias_min=90, sucursal=ALMACEN)['resumen']['capital_total'] == 20
    assert dom.capital_estancado(*args, dias_min=90, sucursal='Barcelona')['resumen']['capital_total'] == 11
    assert dom.capital_estancado(*args, dias_min=200)['articulos'] == []
    assert dom.capital_estancado(None, None, {}, existencias, articulos, 90) is None
