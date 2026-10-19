import io

from conftest import GERENTE, cabeceras

TIENDA = cabeceras('Tienda Barcelona', 'piso_venta')


def test_consulta_de_stock_por_ubicacion(cliente, datos_basicos):
    r = cliente.get('/api/inventario/stock?q=aceite', headers=TIENDA).get_json()
    assert [a['codigo'] for a in r['items']] == ['A1']
    assert r['items'][0]['existencias'] == [
        {'ubicacion': 'Almacén Principal', 'existencia': 100, 'precio_usd': None, 'discrepancia_pendiente': False},
        {'ubicacion': 'Barcelona', 'existencia': 2, 'precio_usd': None, 'discrepancia_pendiente': False},
    ]
    assert cliente.get('/api/inventario/stock?q=A1', headers=TIENDA).get_json()['items'][0]['codigo'] == 'A1'
    assert cliente.get('/api/inventario/stock?q=a', headers=TIENDA).status_code == 400


def test_discrepancia_se_reporta_y_se_revisa(cliente, datos_basicos):
    r = cliente.post('/api/discrepancias', json={'articulo_codigo': 'A1', 'sucursal': 'Barcelona', 'existencia_contada': 0,
                                                 'comentario': 'No hay unidades en el anaquel'}, headers=TIENDA)
    assert r.status_code == 201
    d = r.get_json()['discrepancia']
    assert (d['existencia_sistema'], d['existencia_contada'], d['diferencia'], d['estado']) == (2, 0, -2, 'pendiente')
    assert d['creado_por'] == 'Tienda Barcelona'

    # No se duplica mientras siga pendiente, y la consulta de stock lo indica.
    r = cliente.post('/api/discrepancias', json={'articulo_codigo': 'A1', 'sucursal': 'Barcelona', 'existencia_contada': 1,
                                                 'comentario': 'Otra vez'}, headers=TIENDA)
    assert r.status_code == 409
    existencias = cliente.get('/api/inventario/stock?q=A1', headers=TIENDA).get_json()['items'][0]['existencias']
    assert existencias[1]['discrepancia_pendiente'] is True
    assert cliente.get('/api/dashboard', headers=GERENTE).get_json()['discrepancias_pendientes'] == 1

    assert cliente.patch(f"/api/discrepancias/{d['id']}", json={}, headers=GERENTE).status_code == 400
    r = cliente.patch(f"/api/discrepancias/{d['id']}", json={'resolucion': 'Se ajustó el inventario'}, headers=GERENTE)
    assert r.get_json()['discrepancia']['estado'] == 'revisada'
    assert r.get_json()['discrepancia']['revisado_por'] == 'Carlos Ramírez'
    assert cliente.patch(f"/api/discrepancias/{d['id']}", json={'resolucion': 'De nuevo'}, headers=GERENTE).status_code == 409
    assert cliente.get('/api/discrepancias?estado=pendiente', headers=GERENTE).get_json()['discrepancias'] == []


def test_discrepancia_valida_los_datos(cliente, datos_basicos):
    base = {'articulo_codigo': 'A1', 'sucursal': 'Barcelona', 'existencia_contada': 2, 'comentario': 'Conteo'}
    r = cliente.post('/api/discrepancias', json=base, headers=TIENDA)
    assert r.status_code == 400 and 'coincide' in r.get_json()['error']  # igual al sistema: no es discrepancia
    assert cliente.post('/api/discrepancias', json={**base, 'existencia_contada': 0, 'comentario': ''}, headers=TIENDA).status_code == 400
    assert cliente.post('/api/discrepancias', json={**base, 'sucursal': ''}, headers=TIENDA).status_code == 400
    assert cliente.post('/api/discrepancias', json={**base, 'articulo_codigo': 'X'}, headers=TIENDA).status_code == 400


def test_promociones_se_filtran_por_tipo(cliente, datos_basicos):
    cliente.post('/api/estancado/acciones', json={'articulo_codigo': 'A1', 'tipo': 'promocion'}, headers=GERENTE)
    cliente.post('/api/estancado/acciones', json={'articulo_codigo': 'A1', 'tipo': 'devolucion_proveedor'}, headers=GERENTE)
    acciones = cliente.get('/api/estancado/acciones?tipo=promocion&estado=pendiente', headers=TIENDA).get_json()['acciones']
    assert [a['tipo'] for a in acciones] == ['promocion']


def cargar(cliente, tipo, csv, sucursal=None):
    datos = {'tipo_reporte': tipo, 'archivo': (io.BytesIO(csv.encode()), 'inv.csv')}
    if sucursal:
        datos['sucursal'] = sucursal
    r = cliente.post('/api/carga_inicial', data=datos, content_type='multipart/form-data', headers=GERENTE)
    assert r.status_code == 200, r.get_json()


def test_precio_de_venta_se_importa_por_ubicacion(cliente, datos_basicos):
    # Sucursal: PRECIO1EX en USD (PRECIO1 está en Bs). Almacén: trabaja en USD, PRECIO1EX vacío.
    cargar(cliente, 'inv_fisico', 'CODIGO,NOMBRE,EXISTENCIA,COSTOEX,PRECIO1,PRECIO1EX\nA1,Aceite 1L,4,5,8793,8.62\n', 'Barcelona')
    cargar(cliente, 'inv_inval', 'CDG,NOMBRE,EXISTENCIA,COSTO,PRECIO1,PRECIO1EX\nA1,Aceite 1L,90,5,9.5,0\n')
    existencias = cliente.get('/api/inventario/stock?q=A1', headers=TIENDA).get_json()['items'][0]['existencias']
    assert [(e['ubicacion'], e['existencia'], e['precio_usd']) for e in existencias] == [
        ('Almacén Principal', 90, 9.5), ('Barcelona', 4, 8.62)]


def test_discrepancia_en_el_almacen(cliente, datos_basicos):
    r = cliente.post('/api/discrepancias', json={'articulo_codigo': 'A1', 'sucursal': 'Almacén Principal',
                                                 'existencia_contada': 95, 'comentario': 'Faltan 5 cajas'}, headers=TIENDA)
    assert r.status_code == 201 and r.get_json()['discrepancia']['existencia_sistema'] == 100
