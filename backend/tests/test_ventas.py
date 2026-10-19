from datetime import date

from conftest import GERENTE


def venta(app, grupo, usd, costo, dia=5):
    app.db.session.add(app.Venta(documento='F', articulo_codigo='A1', grupo_venta=grupo, cantidad_neta=1,
                                 precio_fin_moneda_local=usd, factor_sistema=1, factura_real_usd=usd,
                                 costo_real_usd=costo, fecha_emision=date(2026, 11, dia), sucursal='Barcelona'))


def test_utilidad_por_sucursal_y_grupo(cliente, app):
    # Siete grupos: los 5 principales van al gráfico y el resto a OTROS; la tabla completa los trae todos.
    for i, (usd, costo) in enumerate([(100, 60), (90, 50), (80, 40), (70, 35), (60, 30), (20, 10), (10, 0)]):
        venta(app, f'G{i}', usd, costo)
    app.db.session.commit()

    d = cliente.get('/api/ventas/analisis?mes=11&ano=2026&excluir=', headers=GERENTE).get_json()
    assert (d['total_mes'], d['costo_mes'], d['utilidad_mes']) == (430, 225, 205)
    assert d['ventas_sin_costo_mes'] == 10  # G6 no trae costo: su utilidad está inflada y se avisa

    s = d['sucursales'][0]
    assert (s['utilidad'], s['margen']) == (205, 47.7)
    g0 = s['grupos'][0]
    assert (g0['grupo'], g0['total'], g0['costo'], g0['utilidad'], g0['margen']) == ('G0', 100, 60, 40, 40.0)
    otros = s['grupos'][-1]
    assert (otros['grupo'], otros['total'], otros['utilidad']) == ('OTROS', 30, 20)
    assert [g['grupo'] for g in s['todos_los_grupos']] == [f'G{i}' for i in range(7)]
    assert s['todos_los_grupos'][-1]['ventas_sin_costo'] == 10
