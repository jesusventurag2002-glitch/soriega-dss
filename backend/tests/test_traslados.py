import json
from datetime import date, datetime

from conftest import ANALISTA, GERENTE


def agregar_maturin(app):
    """Segunda sucursal sin stock y con la misma venta diaria que Barcelona (2/día)."""
    app.db.session.add(app.Inventario(articulo_codigo='A1', origen_inventario='INV', sucursal='Maturín', existencia=0))
    for dia in (1, 10):
        app.db.session.add(app.Venta(documento='F', articulo_codigo='A1', cantidad_neta=10, precio_fin_moneda_local=1,
                                     factor_sistema=1, factura_real_usd=1, fecha_emision=date(2026, 10, dia),
                                     sucursal='Maturín'))
    app.db.session.commit()


def agregar_jabon(app):
    """Segundo artículo para Barcelona: 50 u en el almacén, 0 en la sucursal y 1/día de venta (15 u con 15 días)."""
    app.db.session.add(app.Articulo(codigo='J1', nombre='Jabón azul', nombredegrupo='LIMPIEZA', costoex=1))
    app.db.session.add(app.Inventario(articulo_codigo='J1', origen_inventario='INVAL', existencia=50))
    app.db.session.add(app.Inventario(articulo_codigo='J1', origen_inventario='INV', sucursal='Barcelona', existencia=0))
    for dia in (1, 10):
        app.db.session.add(app.Venta(documento='F', articulo_codigo='J1', cantidad_neta=5, precio_fin_moneda_local=1,
                                     factor_sistema=1, factura_real_usd=1, fecha_emision=date(2026, 10, dia),
                                     sucursal='Barcelona'))
    app.db.session.commit()


def generar(cliente, dias=15):
    r = cliente.post('/api/traslados/generar', json={'dias': dias}, headers=ANALISTA)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def primer_traslado(cliente, grupo='activos'):
    return cliente.get(f'/api/traslados?grupo={grupo}', headers=ANALISTA).get_json()['items'][0]


def detalle(cliente, d, headers=ANALISTA):
    return cliente.get(f"/api/traslados/{d['id']}", headers=headers).get_json()['traslado']


def accion(cliente, d, nombre, headers=ANALISTA, **extra):
    return cliente.post(f"/api/traslados/{d['id']}/acciones", json={'accion': nombre, 'version': d['version'], **extra},
                        headers=headers)


def linea(d, codigo):
    return next(l for l in d['lineas'] if l['articulo_codigo'] == codigo)


def test_generar_agrupa_articulos_de_la_ruta_en_un_documento(cliente, datos_basicos):
    agregar_jabon(datos_basicos)
    r = generar(cliente)
    assert (r['creados'], r['documentos']) == (2, 1)
    lista = cliente.get('/api/traslados', headers=ANALISTA).get_json()
    assert lista['total'] == 1  # una fila por documento, no por producto
    d = lista['items'][0]
    assert (d['folio'], d['estado'], d['origen'], d['destino']) == ('TR-00001', 'borrador', 'Almacén Principal', 'Barcelona')
    assert (d['total_articulos'], d['total_unidades'], sum(d['abc'].values())) == (2, 43, 2)

    completo = detalle(cliente, d)
    # Prioridad: misma clase ABC, primero el destino con menos cobertura (Jabón: 0 días; Aceite: 1 día).
    assert [l['articulo_codigo'] for l in completo['lineas']] == ['J1', 'A1']
    assert [e['tipo'] for e in completo['eventos']] == ['creado']
    assert completo['eventos'][0]['usuario'] == 'María González'

    # Regenerar no duplica artículos que ya tienen un traslado abierto.
    r = generar(cliente)
    assert (r['creados'], r['omitidos']) == (0, 2)


def test_un_documento_por_sucursal(cliente, datos_basicos):
    agregar_maturin(datos_basicos)
    r = generar(cliente)
    assert r['documentos'] == 2
    destinos = sorted(d['destino'] for d in cliente.get('/api/traslados', headers=ANALISTA).get_json()['items'])
    assert destinos == ['Barcelona', 'Maturín']


def test_nuevas_sugerencias_se_agregan_al_borrador_abierto(cliente, datos_basicos):
    generar(cliente)
    agregar_jabon(datos_basicos)
    r = generar(cliente)
    assert (r['creados'], r['documentos'], r['omitidos']) == (1, 1, 1)
    d = detalle(cliente, primer_traslado(cliente))
    assert d['total_articulos'] == 2
    assert [e['tipo'] for e in d['eventos']] == ['creado', 'articulos_agregados']


def test_ciclo_completo_del_documento_con_diferencias(cliente, datos_basicos):
    agregar_jabon(datos_basicos)
    generar(cliente)
    d = primer_traslado(cliente)

    d = accion(cliente, d, 'enviar').get_json()['traslado']
    assert d['estado'] == 'pendiente_aprobacion'
    assert 'aprobar' not in d['acciones']  # la analista no ve acciones de gerente
    a1, j1 = linea(d, 'A1')['id'], linea(d, 'J1')['id']

    # Un solo clic aprueba todo el documento; solo se ajusta lo que se indica.
    r = accion(cliente, d, 'aprobar', GERENTE, cantidades={str(a1): 20})
    d = r.get_json()['traslado']
    assert d['estado'] == 'aprobado'
    assert (linea(d, 'A1')['cantidad_aprobada'], linea(d, 'J1')['cantidad_aprobada']) == (20, 15)

    d = accion(cliente, d, 'despachar').get_json()['traslado']
    assert d['estado'] == 'despachado' and linea(d, 'A1')['cantidad_despachada'] == 20

    d = accion(cliente, d, 'recibir', cantidades={str(a1): 18, str(j1): 15},
               comentario='Llegaron 2 envases rotos').get_json()['traslado']
    assert d['estado'] == 'recibido_con_diferencias' and d['con_diferencias'] == 1
    assert (linea(d, 'A1')['diferencia'], linea(d, 'J1')['diferencia']) == (-2, 0)

    d = accion(cliente, d, 'cerrar', GERENTE, comentario='Se registró merma de 2 unidades').get_json()['traslado']
    assert d['estado'] == 'cerrado' and d['acciones'] == []

    eventos = d['eventos']
    assert [e['tipo'] for e in eventos] == ['creado', 'enviado_aprobacion', 'aprobado', 'despachado',
                                           'recibido_con_diferencias', 'cerrado']
    aprobado = eventos[2]
    assert aprobado['usuario'] == 'Carlos Ramírez' and aprobado['rol'] == 'gerente'
    assert aprobado['detalle']['despues'] == {'unidades_aprobadas': 35}
    assert aprobado['detalle']['articulos'] == [{'codigo': 'A1', 'nombre': 'Aceite 1L', 'antes': {'cantidad_sugerida': 28},
                                                 'despues': {'cantidad_aprobada': 20}}]
    recibido = eventos[4]
    assert recibido['detalle']['articulos'][0]['despues'] == {'cantidad_recibida': 18, 'diferencia': -2}
    assert recibido['estado_anterior'] == 'despachado'


def test_recepcion_exacta_queda_recibido(cliente, datos_basicos):
    generar(cliente)
    d = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    d = accion(cliente, d, 'aprobar', GERENTE).get_json()['traslado']
    assert d['lineas'][0]['cantidad_aprobada'] == 28  # sin cantidades se aprueba lo sugerido
    d = accion(cliente, d, 'despachar').get_json()['traslado']
    d = accion(cliente, d, 'recibir', cantidades={str(d['lineas'][0]['id']): 28}).get_json()['traslado']
    assert d['estado'] == 'recibido' and d['lineas'][0]['diferencia'] == 0


def test_transiciones_invalidas_se_rechazan(cliente, datos_basicos):
    generar(cliente)
    d = primer_traslado(cliente)
    lid = str(detalle(cliente, d)['lineas'][0]['id'])

    r = accion(cliente, d, 'recibir', cantidades={lid: 5})
    assert r.status_code == 409 and 'borrador' in r.get_json()['error'].lower()
    assert accion(cliente, d, 'aprobar', GERENTE).status_code == 409  # no se aprueba sin enviar
    assert accion(cliente, d, 'inventada').status_code == 400

    d = accion(cliente, d, 'enviar').get_json()['traslado']
    assert accion(cliente, d, 'aprobar', ANALISTA).status_code == 403  # solo gerente
    r = accion(cliente, d, 'rechazar', GERENTE)
    assert r.status_code == 400 and 'motivo' in r.get_json()['error']
    assert accion(cliente, d, 'aprobar', GERENTE, cantidades={'999': 5}).status_code == 400  # artículo ajeno

    d = accion(cliente, d, 'aprobar', GERENTE, cantidades={lid: 10}).get_json()['traslado']
    r = accion(cliente, d, 'despachar', cantidades={lid: 11})
    assert r.status_code == 400 and 'aprobado' in r.get_json()['error']
    assert accion(cliente, d, 'despachar', cantidades={lid: 0}).status_code == 400  # nada despachado
    d = accion(cliente, d, 'despachar', cantidades={lid: 10}).get_json()['traslado']
    r = accion(cliente, d, 'recibir')
    assert r.status_code == 400 and 'cantidad recibida' in r.get_json()['error']
    r = accion(cliente, d, 'recibir', cantidades={lid: 9})
    assert r.status_code == 400 and 'diferencia' in r.get_json()['error']
    assert accion(cliente, d, 'recibir', cantidades={lid: -1}).status_code == 400
    assert accion(cliente, d, 'recibir', cantidades={lid: 'abc'}).status_code == 400

    # Ninguno de los intentos fallidos dejó cambios ni eventos.
    d = detalle(cliente, d)
    assert d['estado'] == 'despachado'
    assert [e['tipo'] for e in d['eventos']] == ['creado', 'enviado_aprobacion', 'aprobado', 'despachado']


def test_rechazo_registra_motivo(cliente, datos_basicos):
    generar(cliente)
    d = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    d = accion(cliente, d, 'rechazar', GERENTE, motivo='Hay una compra en camino').get_json()['traslado']
    assert d['estado'] == 'rechazado' and d['motivo_rechazo'] == 'Hay una compra en camino'
    assert d['eventos'][-1]['detalle']['comentario'] == 'Hay una compra en camino'
    assert cliente.get('/api/traslados?grupo=activos', headers=ANALISTA).get_json()['total'] == 0


def test_doble_envio_no_duplica(cliente, datos_basicos):
    generar(cliente)
    d = primer_traslado(cliente)
    assert accion(cliente, d, 'enviar').status_code == 200
    r = accion(cliente, d, 'enviar')  # misma versión: doble clic u otra pestaña
    assert r.status_code == 409
    cuerpo = r.get_json()
    assert cuerpo['traslado']['estado'] == 'pendiente_aprobacion'  # el cliente recibe el estado real
    assert [e['tipo'] for e in cuerpo['traslado']['eventos']].count('enviado_aprobacion') == 1


def test_no_se_aprueba_mas_que_el_stock_disponible(cliente, datos_basicos):
    generar(cliente)
    d = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    r = accion(cliente, d, 'aprobar', GERENTE, cantidades={str(d['lineas'][0]['id']): 101})
    assert r.status_code == 400 and 'disponibles' in r.get_json()['error']
    assert detalle(cliente, d)['estado'] == 'pendiente_aprobacion'  # ningún artículo quedó aprobado a medias


def test_stock_reservado_por_otros_traslados(cliente, datos_basicos):
    agregar_maturin(datos_basicos)
    generar(cliente)
    a, b = [detalle(cliente, d) for d in cliente.get('/api/traslados?orden=ruta', headers=ANALISTA).get_json()['items']]
    assert a['total_unidades'] + b['total_unidades'] <= 100
    a = accion(cliente, a, 'enviar').get_json()['traslado']
    a = accion(cliente, a, 'aprobar', GERENTE, cantidades={str(a['lineas'][0]['id']): 90}).get_json()['traslado']
    r = cliente.patch(f"/api/traslados/{b['id']}", json={
        'version': b['version'], 'lineas': [{'id': b['lineas'][0]['id'], 'cantidad_sugerida': 20}]}, headers=ANALISTA)
    assert r.status_code == 400 and '10 unidades disponibles' in r.get_json()['error']


def test_editar_cantidades_solo_en_borrador(cliente, datos_basicos):
    agregar_jabon(datos_basicos)
    generar(cliente)
    d = detalle(cliente, primer_traslado(cliente))
    a1, j1 = linea(d, 'A1')['id'], linea(d, 'J1')['id']
    r = cliente.patch(f"/api/traslados/{d['id']}", json={'version': d['version'], 'lineas': [
        {'id': a1, 'cantidad_sugerida': 25}, {'id': j1, 'cantidad_sugerida': 15}]}, headers=ANALISTA)
    d = r.get_json()['traslado']
    assert linea(d, 'A1')['cantidad_sugerida'] == 25
    ultimo = d['eventos'][-1]
    assert ultimo['tipo'] == 'cantidad_modificada'
    # Solo se registra el artículo que realmente cambió.
    assert ultimo['detalle']['articulos'] == [{'codigo': 'A1', 'nombre': 'Aceite 1L', 'antes': {'cantidad_sugerida': 28},
                                               'despues': {'cantidad_sugerida': 25}}]

    d = accion(cliente, d, 'enviar').get_json()['traslado']
    r = cliente.patch(f"/api/traslados/{d['id']}", json={'version': d['version'], 'lineas': [{'id': a1, 'cantidad_sugerida': 5}]},
                      headers=ANALISTA)
    assert r.status_code == 409


def test_quitar_articulo_del_documento(cliente, datos_basicos):
    agregar_jabon(datos_basicos)
    generar(cliente)
    d = detalle(cliente, primer_traslado(cliente))
    j1 = linea(d, 'J1')['id']
    r = cliente.delete(f"/api/traslados/{d['id']}/lineas/{j1}", json={'version': d['version']}, headers=ANALISTA)
    assert r.status_code == 200
    d = r.get_json()['traslado']
    assert [l['articulo_codigo'] for l in d['lineas']] == ['A1'] and d['total_articulos'] == 1
    assert d['eventos'][-1]['tipo'] == 'articulo_retirado'
    assert d['eventos'][-1]['detalle']['articulos'][0]['codigo'] == 'J1'

    # El último artículo no se quita: se descarta el documento completo.
    r = cliente.delete(f"/api/traslados/{d['id']}/lineas/{d['lineas'][0]['id']}", json={'version': d['version']}, headers=ANALISTA)
    assert r.status_code == 400 and 'descarta' in r.get_json()['error']

    # El artículo retirado queda libre para una nueva propuesta, que vuelve al mismo borrador.
    assert generar(cliente)['creados'] == 1
    assert detalle(cliente, d)['total_articulos'] == 2


def test_en_aprobacion_solo_el_gerente_quita_articulos(cliente, datos_basicos):
    agregar_jabon(datos_basicos)
    generar(cliente)
    d = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    assert d['retirable'] is False
    ruta = f"/api/traslados/{d['id']}/lineas/{linea(d, 'J1')['id']}"
    assert cliente.delete(ruta, json={'version': d['version']}, headers=ANALISTA).status_code == 409
    r = cliente.delete(ruta, json={'version': d['version']}, headers=GERENTE)
    assert r.status_code == 200 and r.get_json()['traslado']['retirable'] is True
    d = accion(cliente, r.get_json()['traslado'], 'aprobar', GERENTE).get_json()['traslado']
    assert [l['articulo_codigo'] for l in d['lineas']] == ['A1']


def test_historial_persiste_entre_sesiones(cliente, datos_basicos):
    app = datos_basicos
    generar(cliente)
    d = accion(cliente, primer_traslado(cliente), 'enviar').get_json()['traslado']
    # Simula reiniciar: se descarta la sesión y se consulta de nuevo desde la base.
    app.db.session.remove()
    d = detalle(app.app.test_client(), d, GERENTE)
    assert d['estado'] == 'pendiente_aprobacion'
    assert [e['tipo'] for e in d['eventos']] == ['creado', 'enviado_aprobacion']
    assert 'aprobar' in d['acciones']


def test_bandeja_filtros_conteos_y_paginacion(cliente, datos_basicos):
    agregar_jabon(datos_basicos)
    generar(cliente)
    accion(cliente, primer_traslado(cliente), 'enviar')
    r = cliente.get('/api/traslados?grupo=por_aprobar', headers=GERENTE).get_json()
    assert r['total'] == 1 and r['conteos']['por_aprobar'] == 1 and r['conteos']['borradores'] == 0
    for termino, total in (('aceite', 1), ('jabón', 1), ('TR-00001', 1), ('arroz', 0)):
        assert cliente.get(f'/api/traslados?grupo=activos&q={termino}', headers=GERENTE).get_json()['total'] == total, termino
    assert cliente.get('/api/traslados?grupo=activos&abc=A', headers=GERENTE).get_json()['total'] == 1
    assert cliente.get('/api/traslados?grupo=activos&destino=Maturín', headers=GERENTE).get_json()['total'] == 0
    # Una página que ya no existe devuelve la última válida.
    assert cliente.get('/api/traslados?grupo=activos&pagina=9', headers=GERENTE).get_json()['pagina'] == 1
    assert cliente.get('/api/traslados?grupo=inventado', headers=GERENTE).status_code == 400


def test_lote_es_todo_o_nada(cliente, datos_basicos):
    agregar_maturin(datos_basicos)
    generar(cliente)
    a, b = cliente.get('/api/traslados', headers=ANALISTA).get_json()['items']
    a = accion(cliente, a, 'enviar').get_json()['traslado']  # a ya no es borrador

    r = cliente.post('/api/traslados/lote', json={'accion': 'enviar', 'items': [
        {'id': a['id'], 'version': a['version']}, {'id': b['id'], 'version': b['version']}]}, headers=ANALISTA)
    assert r.status_code == 409 and len(r.get_json()['errores']) == 1
    assert detalle(cliente, b)['estado'] == 'borrador'

    r = cliente.post('/api/traslados/lote', json={'accion': 'enviar', 'items': [{'id': b['id'], 'version': b['version']}]},
                     headers=ANALISTA)
    assert r.status_code == 200 and r.get_json()['traslados'][0]['estado'] == 'pendiente_aprobacion'
    assert cliente.post('/api/traslados/lote', json={'accion': 'aprobar', 'items': [{'id': 1, 'version': 1}]},
                        headers=GERENTE).status_code == 400


def test_retorno_al_almacen(cliente, datos_basicos):
    r = cliente.post('/api/traslados', json={'articulo_codigo': 'A1', 'origen': 'Barcelona', 'cantidad': 2}, headers=ANALISTA)
    assert r.status_code == 201
    d = r.get_json()['traslado']
    assert (d['tipo'], d['origen'], d['destino'], d['estado']) == ('retorno', 'Barcelona', 'Almacén Principal', 'borrador')
    assert d['lineas'][0]['cantidad_sugerida'] == 2
    r = cliente.post('/api/traslados', json={'articulo_codigo': 'A1', 'origen': 'Barcelona', 'cantidad': 1}, headers=ANALISTA)
    assert r.status_code == 409
    r = cliente.post('/api/traslados', json={'articulo_codigo': 'A1', 'origen': 'Maturín', 'cantidad': 1}, headers=ANALISTA)
    assert r.status_code == 400 and 'disponibles' in r.get_json()['error']


def test_traslado_inexistente(cliente, app):
    r = cliente.get('/api/traslados/999', headers=ANALISTA)
    assert r.status_code == 404 and r.get_json()['success'] is False


def test_migracion_agrupa_traslados_por_articulo(cliente, app):
    """Los traslados de un artículo cada uno (modelo anterior) pasan a documentos por ruta con su historial."""
    ahora = datetime(2026, 10, 10, 9, 0)
    viejos = [app.Traslado(articulo_codigo=c, articulo_nombre=n, clasificacion_abc='A', tipo='reposicion',
                           origen='Almacén Principal', destino='Barcelona', estado=e, cantidad_sugerida=5,
                           creado_por='Ana', creado_en=ahora, actualizado_en=ahora)
              for c, n, e in (('A1', 'Aceite', 'borrador'), ('J1', 'Jabón', 'borrador'), ('P1', 'Pico', 'cerrado'))]
    app.db.session.add_all(viejos)
    app.db.session.flush()
    app.db.session.add(app.EventoTraslado(traslado_id=viejos[0].id, tipo='creado', estado_nuevo='borrador', usuario='Ana',
                                          fecha=ahora, detalle=json.dumps({'comentario': 'Propuesta'})))
    app.db.session.commit()

    app.agrupar_traslados_en_documentos()
    app.agrupar_traslados_en_documentos()  # idempotente

    borradores = cliente.get('/api/traslados?grupo=borradores', headers=ANALISTA).get_json()
    assert borradores['total'] == 1 and borradores['items'][0]['total_articulos'] == 2
    assert cliente.get('/api/traslados?grupo=cerrados', headers=ANALISTA).get_json()['total'] == 1
    eventos = detalle(cliente, borradores['items'][0])['eventos']
    assert eventos[0]['detalle'] == {'comentario': 'Propuesta', 'articulos': [{'codigo': 'A1', 'nombre': 'Aceite'}]}


def test_generar_respeta_las_clases_abc_elegidas(cliente, datos_basicos):
    app = datos_basicos
    # P1 vende 1 u frente a las 20 de A1: queda en clase C pero Barcelona también lo necesita.
    app.db.session.add(app.Articulo(codigo='P1', nombre='Pico dosificador', nombredegrupo='VARIOS', costoex=1))
    app.db.session.add(app.Inventario(articulo_codigo='P1', origen_inventario='INVAL', existencia=10))
    app.db.session.add(app.Inventario(articulo_codigo='P1', origen_inventario='INV', sucursal='Barcelona', existencia=0))
    app.db.session.add(app.Venta(documento='F', articulo_codigo='P1', cantidad_neta=1, precio_fin_moneda_local=1,
                                 factor_sistema=1, factura_real_usd=1, fecha_emision=date(2026, 10, 5), sucursal='Barcelona'))
    app.db.session.commit()

    r = cliente.post('/api/traslados/generar', json={'dias': 15, 'clases': ['A']}, headers=ANALISTA).get_json()
    assert r['creados'] == 1
    assert [l['articulo_codigo'] for l in detalle(cliente, primer_traslado(cliente))['lineas']] == ['A1']

    # Luego se pueden sumar las demás clases al mismo borrador.
    assert generar(cliente)['creados'] == 1
    assert {l['clasificacion_abc'] for l in detalle(cliente, primer_traslado(cliente))['lineas']} == {'A', 'C'}
    assert cliente.post('/api/traslados/generar', json={'clases': ['X']}, headers=ANALISTA).status_code == 400
