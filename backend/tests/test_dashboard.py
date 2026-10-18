import io

from conftest import ANALISTA, GERENTE


def test_dashboard_cuenta_pendientes_y_criticos(cliente, datos_basicos):
    d = cliente.get('/api/dashboard', headers=GERENTE).get_json()
    assert d['traslados']['por_aprobar'] == 0
    # A1 es clase A: 2 u en Barcelona con venta de 2/día = 1 día de cobertura (< 7).
    assert d['criticos']['total'] == 1
    critico = d['criticos']['items'][0]
    assert (critico['sucursal'], critico['cobertura_dias'], critico['traslado']) == ('Barcelona', 1.0, None)

    cliente.post('/api/traslados/generar', json={'dias': 15}, headers=ANALISTA)
    t = cliente.get('/api/traslados', headers=ANALISTA).get_json()['items'][0]
    cliente.post(f"/api/traslados/{t['id']}/acciones", json={'accion': 'enviar', 'version': t['version']}, headers=ANALISTA)

    d = cliente.get('/api/dashboard', headers=GERENTE).get_json()
    assert d['traslados']['por_aprobar'] == 1
    assert d['pendientes']['por_aprobar'][0]['folio'] == 'TR-00001'
    assert d['criticos']['items'][0]['traslado']['estado'] == 'pendiente_aprobacion'  # enlaza al traslado abierto
    assert [a['tipo'] for a in d['actividad']] == ['enviado_aprobacion', 'creado']
    assert d['capital_estancado'] is not None and d['capital_estancado']['consolidado'] is True

    # Vista por sucursal: otra sucursal no ve los traslados ni los críticos de Barcelona.
    otra = cliente.get('/api/dashboard?sucursal=Maturín', headers=GERENTE).get_json()
    assert otra['traslados']['por_aprobar'] == 0 and otra['criticos']['total'] == 0 and otra['actividad'] == []


def test_sin_inventario_no_se_inventan_criticos(cliente, datos_basicos):
    app = datos_basicos
    app.Inventario.query.filter_by(origen_inventario='INV').delete()
    app.db.session.commit()
    assert cliente.get('/api/inventario/criticos', headers=GERENTE).get_json()['items'] == []


def test_estado_de_los_datos_e_importaciones(cliente, datos_basicos):
    csv = 'CODIGO,NOMBRE,EXISTENCIA,COSTOEX\nA1,Aceite 1L,5,5\n'.encode()
    r = cliente.post('/api/carga_inicial', data={'tipo_reporte': 'inv_fisico', 'sucursal': 'Barcelona',
                                                  'archivo': (io.BytesIO(csv), 'inv.csv')},
                     content_type='multipart/form-data', headers=ANALISTA)
    assert r.status_code == 200
    r = cliente.post('/api/carga_inicial', data={'tipo_reporte': 'ventas', 'sucursal': 'Barcelona',
                                                  'archivo': (io.BytesIO(b'x'), 'malo.txt')},
                     content_type='multipart/form-data', headers=ANALISTA)
    assert r.status_code == 400

    imps = cliente.get('/api/importaciones', headers=ANALISTA).get_json()['importaciones']
    assert [(i['tipo_reporte'], i['exito']) for i in imps] == [('ventas', False), ('inv_fisico', True)]
    assert imps[1]['usuario'] == 'María González'

    datos = cliente.get('/api/dashboard', headers=GERENTE).get_json()['datos']
    barcelona = datos['sucursales'][0]
    assert barcelona['inventario']['cargado'] and barcelona['inventario']['importado_en']
    # Ventas cargadas antes de registrar importaciones: se sabe hasta qué fecha llegan, no cuándo se importaron.
    assert barcelona['ventas']['datos_hasta'] == '2026-10-10' and barcelona['ventas']['importado_en'] is None


def test_capital_estancado_consolidado_y_por_ubicacion(cliente, datos_basicos):
    # A1: 100 u en almacén + 2 u en Barcelona, costo 5. Consolidado = 102 u; por ubicación, solo la suya.
    def capital(params=''):
        return cliente.get(f'/api/capital_estancado?dias_min=0{params}', headers=GERENTE).get_json()['articulos'][0]

    total = capital()
    assert (total['existencia'], total['existencia_almacen'], total['capital_estancado']) == (102, 100, 510.0)
    assert capital('&sucursal=Barcelona')['existencia'] == 2
    assert capital('&sucursal=Almacén Principal')['existencia'] == 100


def test_acciones_de_mercancia_estancada(cliente, datos_basicos):
    r = cliente.post('/api/estancado/acciones', json={'articulo_codigo': 'A1', 'tipo': 'promocion', 'capital': 510},
                     headers=GERENTE)
    assert r.status_code == 201
    accion = r.get_json()['accion']
    assert (accion['estado'], accion['creado_por']) == ('pendiente', 'Carlos Ramírez')
    assert cliente.post('/api/estancado/acciones', json={'articulo_codigo': 'A1', 'tipo': 'promocion'},
                        headers=GERENTE).status_code == 409  # sin duplicados pendientes

    r = cliente.patch(f"/api/estancado/acciones/{accion['id']}", json={'estado': 'completada'}, headers=GERENTE)
    assert r.status_code == 400  # exige resultado
    r = cliente.patch(f"/api/estancado/acciones/{accion['id']}", json={'estado': 'completada', 'resultado': 'Vendidas 10 u'},
                      headers=GERENTE)
    assert r.get_json()['accion']['estado'] == 'completada'
    assert cliente.patch(f"/api/estancado/acciones/{accion['id']}", json={'estado': 'descartada'},
                         headers=GERENTE).status_code == 409

    estancado = cliente.get('/api/capital_estancado?dias_min=0', headers=GERENTE).get_json()
    assert estancado['articulos'][0]['acciones'][0]['resultado'] == 'Vendidas 10 u'
