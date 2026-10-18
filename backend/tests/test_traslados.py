from datetime import date

from conftest import ANALISTA, GERENTE


def agregar_maturin(app):
    """Segunda sucursal sin stock y con la misma venta diaria que Barcelona (2/día)."""
    app.db.session.add(app.Inventario(articulo_codigo='A1', origen_inventario='INV', sucursal='Maturín', existencia=0))
    for dia in (1, 10):
        app.db.session.add(app.Venta(documento='F', articulo_codigo='A1', cantidad_neta=10, precio_fin_moneda_local=1,
                                     factor_sistema=1, factura_real_usd=1, fecha_emision=date(2026, 10, dia),
                                     sucursal='Maturín'))
    app.db.session.commit()


def generar(cliente, dias=15):
    r = cliente.post('/api/traslados/generar', json={'dias': dias}, headers=ANALISTA)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def primer_traslado(cliente, grupo='activos'):
    return cliente.get(f'/api/traslados?grupo={grupo}', headers=ANALISTA).get_json()['items'][0]


def accion(cliente, t, nombre, headers=ANALISTA, **extra):
    return cliente.post(f"/api/traslados/{t['id']}/acciones", json={'accion': nombre, 'version': t['version'], **extra},
                        headers=headers)


def test_generar_crea_borradores_sin_duplicar(cliente, datos_basicos):
    r = generar(cliente)
    assert r['creados'] == 1
    t = primer_traslado(cliente)
    assert (t['estado'], t['origen'], t['destino'], t['cantidad_sugerida']) == ('borrador', 'Almacén Principal', 'Barcelona', 28)
    assert t['folio'] == 'TR-00001'

    # Regenerar no duplica el artículo que ya tiene un traslado abierto.
    r = generar(cliente)
    assert (r['creados'], r['omitidos']) == (0, 1)

    detalle = cliente.get(f"/api/traslados/{t['id']}", headers=ANALISTA).get_json()['traslado']
    assert [e['tipo'] for e in detalle['eventos']] == ['creado']
    assert detalle['eventos'][0]['usuario'] == 'María González'


def test_ciclo_completo_con_diferencias_y_trazabilidad(cliente, datos_basicos):
    generar(cliente)
    t = primer_traslado(cliente)

    r = accion(cliente, t, 'enviar')
    assert r.status_code == 200
    t = r.get_json()['traslado']
    assert t['estado'] == 'pendiente_aprobacion'
    assert 'aprobar' not in t['acciones']  # la analista no ve acciones de gerente

    r = accion(cliente, t, 'aprobar', GERENTE, cantidad=20)
    t = r.get_json()['traslado']
    assert (t['estado'], t['cantidad_aprobada']) == ('aprobado', 20)

    t = accion(cliente, t, 'despachar', cantidad=20).get_json()['traslado']
    assert (t['estado'], t['cantidad_despachada']) == ('despachado', 20)

    t = accion(cliente, t, 'recibir', cantidad=18, comentario='Llegaron 2 envases rotos').get_json()['traslado']
    assert (t['estado'], t['cantidad_recibida'], t['diferencia']) == ('recibido_con_diferencias', 18, -2)

    r = accion(cliente, t, 'cerrar', GERENTE, comentario='Se registró merma de 2 unidades')
    t = r.get_json()['traslado']
    assert t['estado'] == 'cerrado' and t['acciones'] == []

    eventos = t['eventos']
    assert [e['tipo'] for e in eventos] == ['creado', 'enviado_aprobacion', 'aprobado', 'despachado',
                                           'recibido_con_diferencias', 'cerrado']
    aprobado = eventos[2]
    assert aprobado['usuario'] == 'Carlos Ramírez' and aprobado['rol'] == 'gerente'
    assert aprobado['detalle'] == {'antes': {'cantidad_sugerida': 28}, 'despues': {'cantidad_aprobada': 20}}
    assert eventos[4]['detalle']['despues'] == {'cantidad_recibida': 18, 'diferencia': -2}
    assert eventos[4]['estado_anterior'] == 'despachado'


def test_recepcion_exacta_queda_recibido(cliente, datos_basicos):
    generar(cliente)
    t = primer_traslado(cliente)
    t = accion(cliente, t, 'enviar').get_json()['traslado']
    t = accion(cliente, t, 'aprobar', GERENTE).get_json()['traslado']
    assert t['cantidad_aprobada'] == 28  # sin cantidad se aprueba la sugerida
    t = accion(cliente, t, 'despachar').get_json()['traslado']
    t = accion(cliente, t, 'recibir', cantidad=28).get_json()['traslado']
    assert t['estado'] == 'recibido' and t['diferencia'] == 0


def test_transiciones_invalidas_se_rechazan(cliente, datos_basicos):
    generar(cliente)
    t = primer_traslado(cliente)

    r = accion(cliente, t, 'recibir', cantidad=5)
    assert r.status_code == 409 and 'borrador' in r.get_json()['error'].lower()
    assert accion(cliente, t, 'aprobar', GERENTE).status_code == 409  # no se aprueba sin enviar
    assert accion(cliente, t, 'inventada').status_code == 400

    t = accion(cliente, t, 'enviar').get_json()['traslado']
    assert accion(cliente, t, 'aprobar', ANALISTA).status_code == 403  # solo gerente
    r = accion(cliente, t, 'rechazar', GERENTE)
    assert r.status_code == 400 and 'motivo' in r.get_json()['error']

    t = accion(cliente, t, 'aprobar', GERENTE, cantidad=10).get_json()['traslado']
    r = accion(cliente, t, 'despachar', cantidad=11)
    assert r.status_code == 400 and 'aprobado' in r.get_json()['error']
    t = accion(cliente, t, 'despachar', cantidad=10).get_json()['traslado']
    r = accion(cliente, t, 'recibir', cantidad=9)
    assert r.status_code == 400 and 'diferencia' in r.get_json()['error']
    assert accion(cliente, t, 'recibir', cantidad=-1).status_code == 400
    assert accion(cliente, t, 'recibir', cantidad='abc').status_code == 400

    # Ninguno de los intentos fallidos dejó cambios ni eventos.
    detalle = cliente.get(f"/api/traslados/{t['id']}", headers=ANALISTA).get_json()['traslado']
    assert detalle['estado'] == 'despachado'
    assert [e['tipo'] for e in detalle['eventos']] == ['creado', 'enviado_aprobacion', 'aprobado', 'despachado']


def test_rechazo_registra_motivo(cliente, datos_basicos):
    generar(cliente)
    t = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    t = accion(cliente, t, 'rechazar', GERENTE, motivo='Hay una compra en camino').get_json()['traslado']
    assert t['estado'] == 'rechazado' and t['motivo_rechazo'] == 'Hay una compra en camino'
    assert t['eventos'][-1]['detalle']['comentario'] == 'Hay una compra en camino'


def test_doble_envio_no_duplica(cliente, datos_basicos):
    generar(cliente)
    t = primer_traslado(cliente)
    assert accion(cliente, t, 'enviar').status_code == 200
    r = accion(cliente, t, 'enviar')  # misma versión: doble clic u otra pestaña
    assert r.status_code == 409
    cuerpo = r.get_json()
    assert cuerpo['traslado']['estado'] == 'pendiente_aprobacion'  # el cliente recibe el estado real
    assert [e['tipo'] for e in cuerpo['traslado']['eventos']].count('enviado_aprobacion') == 1


def test_no_se_aprueba_mas_que_el_stock_disponible(cliente, datos_basicos):
    generar(cliente)
    t = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    r = accion(cliente, t, 'aprobar', GERENTE, cantidad=101)
    assert r.status_code == 400 and 'disponibles' in r.get_json()['error']


def test_stock_reservado_por_otros_traslados(cliente, datos_basicos):
    app = datos_basicos
    # Segunda sucursal con la misma necesidad: entre ambas reservas no se puede superar el almacén.
    agregar_maturin(app)
    generar(cliente)
    items = cliente.get('/api/traslados', headers=ANALISTA).get_json()['items']
    assert sum(i['cantidad_sugerida'] for i in items) <= 100
    a, b = items
    a = accion(cliente, a, 'enviar').get_json()['traslado']
    a = accion(cliente, a, 'aprobar', GERENTE, cantidad=90).get_json()['traslado']
    r = cliente.patch(f"/api/traslados/{b['id']}", json={'version': b['version'], 'cantidad_sugerida': 20}, headers=ANALISTA)
    assert r.status_code == 400 and '10 unidades disponibles' in r.get_json()['error']


def test_editar_cantidad_solo_en_borrador(cliente, datos_basicos):
    generar(cliente)
    t = primer_traslado(cliente)
    r = cliente.patch(f"/api/traslados/{t['id']}", json={'version': t['version'], 'cantidad_sugerida': 25}, headers=ANALISTA)
    t = r.get_json()['traslado']
    assert t['cantidad_sugerida'] == 25
    assert t['eventos'][-1]['tipo'] == 'cantidad_modificada'
    assert t['eventos'][-1]['detalle'] == {'antes': {'cantidad_sugerida': 28}, 'despues': {'cantidad_sugerida': 25}}

    t = accion(cliente, t, 'enviar').get_json()['traslado']
    r = cliente.patch(f"/api/traslados/{t['id']}", json={'version': t['version'], 'cantidad_sugerida': 5}, headers=ANALISTA)
    assert r.status_code == 409


def test_historial_persiste_entre_sesiones(cliente, datos_basicos):
    app = datos_basicos
    generar(cliente)
    t = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    # Simula reiniciar: se descarta la sesión y se consulta de nuevo desde la base.
    app.db.session.remove()
    detalle = app.app.test_client().get(f"/api/traslados/{t['id']}", headers=GERENTE).get_json()['traslado']
    assert detalle['estado'] == 'pendiente_aprobacion'
    assert [e['tipo'] for e in detalle['eventos']] == ['creado', 'enviado_aprobacion']
    assert 'aprobar' in detalle['acciones']


def test_bandeja_filtros_conteos_y_paginacion(cliente, datos_basicos):
    generar(cliente)
    t = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    r = cliente.get('/api/traslados?grupo=por_aprobar', headers=GERENTE).get_json()
    assert r['total'] == 1 and r['conteos']['por_aprobar'] == 1 and r['conteos']['borradores'] == 0
    assert cliente.get('/api/traslados?grupo=activos&q=aceite', headers=GERENTE).get_json()['total'] == 1
    assert cliente.get('/api/traslados?grupo=activos&q=TR-00001', headers=GERENTE).get_json()['total'] == 1
    assert cliente.get('/api/traslados?grupo=activos&q=jabon', headers=GERENTE).get_json()['total'] == 0
    assert cliente.get('/api/traslados?grupo=activos&destino=Maturín', headers=GERENTE).get_json()['total'] == 0
    # Una página que ya no existe devuelve la última válida.
    assert cliente.get('/api/traslados?grupo=activos&pagina=9', headers=GERENTE).get_json()['pagina'] == 1
    assert cliente.get('/api/traslados?grupo=inventado', headers=GERENTE).status_code == 400


def test_lote_es_todo_o_nada(cliente, datos_basicos):
    app = datos_basicos
    agregar_maturin(app)
    generar(cliente)
    a, b = cliente.get('/api/traslados', headers=ANALISTA).get_json()['items']
    a = accion(cliente, a, 'enviar').get_json()['traslado']  # a ya no es borrador

    r = cliente.post('/api/traslados/lote', json={'accion': 'enviar', 'items': [
        {'id': a['id'], 'version': a['version']}, {'id': b['id'], 'version': b['version']}]}, headers=ANALISTA)
    assert r.status_code == 409 and len(r.get_json()['errores']) == 1
    assert cliente.get(f"/api/traslados/{b['id']}", headers=ANALISTA).get_json()['traslado']['estado'] == 'borrador'

    r = cliente.post('/api/traslados/lote', json={'accion': 'enviar', 'items': [{'id': b['id'], 'version': b['version']}]},
                     headers=ANALISTA)
    assert r.status_code == 200 and r.get_json()['traslados'][0]['estado'] == 'pendiente_aprobacion'
    assert cliente.post('/api/traslados/lote', json={'accion': 'aprobar', 'items': [{'id': 1, 'version': 1}]},
                        headers=GERENTE).status_code == 400


def test_retorno_al_almacen(cliente, datos_basicos):
    r = cliente.post('/api/traslados', json={'articulo_codigo': 'A1', 'origen': 'Barcelona', 'cantidad': 2}, headers=ANALISTA)
    assert r.status_code == 201
    t = r.get_json()['traslado']
    assert (t['tipo'], t['origen'], t['destino'], t['estado']) == ('retorno', 'Barcelona', 'Almacén Principal', 'borrador')
    r = cliente.post('/api/traslados', json={'articulo_codigo': 'A1', 'origen': 'Barcelona', 'cantidad': 1}, headers=ANALISTA)
    assert r.status_code == 409
    r = cliente.post('/api/traslados', json={'articulo_codigo': 'A1', 'origen': 'Maturín', 'cantidad': 1}, headers=ANALISTA)
    assert r.status_code == 400 and 'disponibles' in r.get_json()['error']


def test_traslado_inexistente(cliente, app):
    r = cliente.get('/api/traslados/999', headers=ANALISTA)
    assert r.status_code == 404 and r.get_json()['success'] is False
