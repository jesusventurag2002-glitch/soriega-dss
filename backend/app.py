import io
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import unquote

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import and_, case, func, inspect, or_, text, true

from adaptadores.entrada.http import estado_http, usuario_actual
from adaptadores.entrada.demanda import crear_blueprint as blueprint_demanda
from adaptadores.entrada.ventas import crear_blueprint as blueprint_ventas
from adaptadores.entrada.importacion import crear_blueprint as blueprint_importacion
from adaptadores.entrada.traslados import crear_blueprint as blueprint_traslados, resumen_documento, serializar_evento
from adaptadores.salida.migraciones import agrupar_traslados_en_documentos, migrar_esquema  # noqa: F401 (pruebas)
from adaptadores.salida.lector_pandas import LectorPandas
from adaptadores.salida.repo_cargas import RepositorioCargasSQL
from adaptadores.salida.repo_demanda import RepositorioDemandaSQL
from adaptadores.salida.repo_inventario import InventarioSQL
from adaptadores.salida.repo_ventas import RepositorioVentasSQL
from adaptadores.salida.repo_traslados import ORDENES, RepositorioTrasladosSQL
from aplicacion.demanda import CasosDemanda
from aplicacion.importacion import CasosImportacion
from aplicacion.traslados import CasosTraslados
from aplicacion.ventas import CasosVentas
from dominio.comun import entero, numero, texto
from dominio.demanda import DIAS_COBERTURA_CRITICA
from dominio.errores import Conflicto, ErrorDominio
from dominio.traslados import ALMACEN, ESTADOS_ABIERTOS, cantidad_vigente, folio
from dominio.ventas import EXCEPCIONES
from adaptadores.salida.modelos import (
    AccionEstancado, Articulo, ConfigExcepcion, Discrepancia, DocumentoTraslado, EventoDocumento, EventoTraslado,
    Importacion, Inventario, TasaInterna, Traslado, Venta, db,
)

app = Flask(__name__)

# Conexión a PostgreSQL. Se puede sobrescribir con la variable de entorno DATABASE_URL.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql+psycopg://usuario:password@localhost:5432/dss_inventario'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB por archivo
db.init_app(app)

# Orígenes permitidos para el frontend React (Vite: 5173, CRA: 3000).
ORIGENES_FRONTEND = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
CORS(app, resources={r'/api/*': {'origins': ORIGENES_FRONTEND}})


# ==================== API ====================
@app.route('/api/capital_estancado', methods=['GET'])
def capital_estancado():
    dias_min = request.args.get('dias_min', default=90, type=int)
    limite = request.args.get('limite', default=100, type=int)
    datos = casos_demanda.capital_estancado(dias_min, texto(request.args.get('sucursal')) or None)
    if datos is None:
        return jsonify(success=False, error="No hay historial de ventas cargado."), 400

    articulos = datos['articulos'][:limite]
    # Seguimiento de cada artículo: acciones registradas y retornos al almacén en curso.
    codigos = [a['codigo'] for a in articulos]
    acciones = {}
    for accion in AccionEstancado.query.filter(AccionEstancado.articulo_codigo.in_(codigos)).order_by(AccionEstancado.creado_en.desc()):
        acciones.setdefault(accion.articulo_codigo, []).append(serializar_accion(accion))
    retornos = {}
    for t in Traslado.query.filter(Traslado.articulo_codigo.in_(codigos), Traslado.tipo == 'retorno',
                                   Traslado.estado.in_(ESTADOS_ABIERTOS)):
        retornos.setdefault(t.articulo_codigo, []).append(
            {'id': t.documento_id, 'folio': folio(t.documento), 'origen': t.origen, 'estado': t.estado,
             'cantidad': cantidad_vigente(t)})
    for a in articulos:
        a['acciones'] = acciones.get(a['codigo'], [])
        a['retornos'] = retornos.get(a['codigo'], [])

    sucursales = sorted(s for (s,) in db.session.query(Inventario.sucursal).filter(
        Inventario.origen_inventario == 'INV').distinct() if s)
    return jsonify(success=True, **{**datos, 'articulos': articulos, 'sucursales': sucursales})


# ==================== CENTRO DE DECISIONES ====================
def estado_de_los_datos():
    """Qué datos hay cargados por ubicación, cuándo se importaron y hasta qué fecha llegan."""
    def ultima(tipo, sucursal=None):
        q = Importacion.query.filter_by(tipo_reporte=tipo, exito=True)
        if sucursal is not None:
            q = q.filter_by(sucursal=sucursal)
        i = q.order_by(Importacion.fecha_importacion.desc()).first()
        return {'importado_en': i.fecha_importacion.isoformat(timespec='seconds') if i else None,
                'datos_hasta': i.datos_hasta.isoformat() if i and i.datos_hasta else None}

    con_inventario = {s for (s,) in db.session.query(Inventario.sucursal).filter(Inventario.origen_inventario == 'INV').distinct() if s}
    ventas_hasta = dict(db.session.query(Venta.sucursal, func.max(Venta.fecha_emision)).group_by(Venta.sucursal).all())
    sucursales = sorted(con_inventario | {s for s in ventas_hasta if s})
    tasas_hasta = db.session.query(func.max(TasaInterna.fecha)).filter(TasaInterna.tasa_paralelo.isnot(None)).scalar()
    return {
        'sucursales': [{
            'sucursal': s,
            'inventario': {'cargado': s in con_inventario, **ultima('inv_fisico', s)},
            # La fecha de los datos de ventas se toma de las propias ventas (última emisión), no de la importación.
            'ventas': {'cargado': s in ventas_hasta, **ultima('ventas', s),
                       'datos_hasta': ventas_hasta[s].isoformat() if s in ventas_hasta else None},
        } for s in sucursales],
        'almacen': {'cargado': Inventario.query.filter_by(origen_inventario='INVAL').first() is not None, **ultima('inv_inval')},
        'tasas': {**ultima('tasas'), 'datos_hasta': tasas_hasta.isoformat() if tasas_hasta else None},
        'ventas_sin_sucursal': None in ventas_hasta,
    }


@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    """Indicadores, pendientes y actividad para el centro de decisiones; ?sucursal= para la vista individual."""
    sucursal = texto(request.args.get('sucursal')) or None
    traslados = DocumentoTraslado.query
    if sucursal:
        traslados = traslados.filter(or_(DocumentoTraslado.origen == sucursal, DocumentoTraslado.destino == sucursal))
    por_estado = dict(traslados.with_entities(DocumentoTraslado.estado, func.count()).group_by(DocumentoTraslado.estado).all())

    def lista(estados, orden, limite=5):
        return [resumen_documento(d) for d in traslados.filter(DocumentoTraslado.estado.in_(estados)).order_by(*orden).limit(limite)]

    criticos = casos_demanda.productos_criticos(sucursal)
    capital = casos_demanda.capital_estancado(90, sucursal)
    acciones = AccionEstancado.query.filter_by(estado='pendiente').order_by(AccionEstancado.creado_en)
    discrepancias = Discrepancia.query.filter_by(estado='pendiente')
    if sucursal:
        discrepancias = discrepancias.filter_by(sucursal=sucursal)

    actividad = db.session.query(EventoDocumento, DocumentoTraslado).join(
        DocumentoTraslado, DocumentoTraslado.id == EventoDocumento.documento_id)
    if sucursal:
        actividad = actividad.filter(or_(DocumentoTraslado.origen == sucursal, DocumentoTraslado.destino == sucursal))
    actividad = actividad.order_by(EventoDocumento.fecha.desc(), EventoDocumento.id.desc()).limit(10).all()

    return jsonify(
        success=True,
        sucursal=sucursal,
        generado_en=datetime.now().isoformat(timespec='seconds'),
        traslados={
            'borradores': por_estado.get('borrador', 0),
            'por_aprobar': por_estado.get('pendiente_aprobacion', 0),
            'por_despachar': por_estado.get('aprobado', 0),
            'en_transito': por_estado.get('despachado', 0),
            'con_diferencias': por_estado.get('recibido_con_diferencias', 0),
            'por_cerrar': por_estado.get('recibido', 0) + por_estado.get('recibido_con_diferencias', 0),
        },
        pendientes={
            'por_aprobar': lista(['pendiente_aprobacion'], ORDENES['prioridad']),
            'en_transito': lista(['despachado'], [DocumentoTraslado.actualizado_en]),
            'con_diferencias': lista(['recibido_con_diferencias'], [DocumentoTraslado.actualizado_en]),
        },
        criticos={'total': len(criticos), 'dias_cobertura': DIAS_COBERTURA_CRITICA, 'items': criticos[:5]},
        capital_estancado=None if capital is None else {
            'total': capital['resumen']['capital_total'], 'articulos': capital['resumen']['articulos'],
            'dias_min': capital['dias_min'], 'fecha_corte': capital['fecha_corte'],
            'consolidado': sucursal is None,
        },
        acciones_estancado={'pendientes': acciones.count(), 'items': [serializar_accion(a) for a in acciones.limit(5)]},
        discrepancias_pendientes=discrepancias.count(),
        actividad=[{**serializar_evento(e), 'traslado': resumen_documento(d)} for e, d in actividad],
        importaciones=[serializar_importacion(i) for i in Importacion.query.order_by(Importacion.fecha_importacion.desc()).limit(5)],
        datos=estado_de_los_datos(),
    )


def serializar_importacion(i):
    return {'id': i.id, 'tipo_reporte': i.tipo_reporte, 'sucursal': i.sucursal, 'archivo': i.archivo, 'exito': i.exito,
            'mensaje': i.mensaje, 'fecha_importacion': i.fecha_importacion.isoformat(timespec='seconds'),
            'datos_hasta': i.datos_hasta.isoformat() if i.datos_hasta else None, 'usuario': i.usuario}


@app.route('/api/importaciones', methods=['GET'])
def listar_importaciones():
    return jsonify(success=True, importaciones=[
        serializar_importacion(i) for i in Importacion.query.order_by(Importacion.fecha_importacion.desc()).limit(50)])


# ==================== SEGUIMIENTO DE MERCANCÍA ESTANCADA ====================
TIPOS_ACCION_ESTANCADO = {'promocion': 'Descuento / promoción', 'devolucion_proveedor': 'Devolución a proveedor'}


def serializar_accion(a):
    return {
        'id': a.id, 'articulo_codigo': a.articulo_codigo, 'articulo_nombre': a.articulo_nombre, 'tipo': a.tipo,
        'tipo_etiqueta': TIPOS_ACCION_ESTANCADO[a.tipo], 'estado': a.estado,
        'capital_al_registrar': float(a.capital_al_registrar) if a.capital_al_registrar is not None else None,
        'comentario': a.comentario, 'resultado': a.resultado, 'creado_por': a.creado_por,
        'creado_en': a.creado_en.isoformat(timespec='seconds'), 'cerrado_por': a.cerrado_por,
        'cerrado_en': a.cerrado_en.isoformat(timespec='seconds') if a.cerrado_en else None,
    }


@app.route('/api/estancado/acciones', methods=['GET'])
def listar_acciones_estancado():
    q = AccionEstancado.query
    for campo in ('estado', 'tipo'):
        if request.args.get(campo):
            q = q.filter(getattr(AccionEstancado, campo) == request.args[campo])
    return jsonify(success=True, acciones=[serializar_accion(a) for a in q.order_by(AccionEstancado.creado_en.desc()).limit(200)])


@app.route('/api/estancado/acciones', methods=['POST'])
def registrar_accion_estancado():
    """{"articulo_codigo", "tipo": "promocion" | "devolucion_proveedor", "comentario", "capital"}"""
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    codigo, tipo = texto(datos.get('articulo_codigo')), datos.get('tipo')
    art = db.session.get(Articulo, codigo) if codigo else None
    if art is None:
        return jsonify(success=False, error="El artículo no existe."), 400
    if tipo not in TIPOS_ACCION_ESTANCADO:
        return jsonify(success=False, error="Tipo de acción inválido."), 400
    if AccionEstancado.query.filter_by(articulo_codigo=codigo, tipo=tipo, estado='pendiente').first():
        return jsonify(success=False, error=f"Ya hay una acción «{TIPOS_ACCION_ESTANCADO[tipo]}» pendiente para este artículo."), 409
    accion = AccionEstancado(
        articulo_codigo=codigo, articulo_nombre=art.nombre, tipo=tipo, estado='pendiente',
        capital_al_registrar=numero(datos.get('capital'), None), comentario=texto(datos.get('comentario')) or None,
        creado_por=usuario[0], creado_en=datetime.now(),
    )
    db.session.add(accion)
    db.session.commit()
    return jsonify(success=True, accion=serializar_accion(accion)), 201


@app.route('/api/estancado/acciones/<int:id_>', methods=['PATCH'])
def cerrar_accion_estancado(id_):
    """{"estado": "completada" | "descartada", "resultado": "..."}; solo desde pendiente."""
    datos = request.get_json(silent=True) or {}
    accion = db.session.get(AccionEstancado, id_)
    if accion is None:
        return jsonify(success=False, error="La acción no existe."), 404
    estado, resultado = datos.get('estado'), texto(datos.get('resultado'))
    if accion.estado != 'pendiente':
        return jsonify(success=False, error="La acción ya fue cerrada.", accion=serializar_accion(accion)), 409
    if estado not in ('completada', 'descartada'):
        return jsonify(success=False, error="Estado inválido."), 400
    if estado == 'completada' and len(resultado) < 3:
        return jsonify(success=False, error="Describe el resultado obtenido."), 400
    accion.estado, accion.resultado = estado, resultado or None
    accion.cerrado_por, accion.cerrado_en = usuario_actual()[0], datetime.now()
    db.session.commit()
    return jsonify(success=True, accion=serializar_accion(accion))


# ==================== PISO DE VENTA ====================
def existencias_por_ubicacion(codigos):
    """{codigo: {ubicación: (existencia, precio USD sin IVA)}} del almacén principal y cada sucursal cargada."""
    resultado = {}
    for codigo, origen, sucursal, total, precio in db.session.query(
        Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia),
        func.max(Inventario.precio_usd),
    ).filter(Inventario.articulo_codigo.in_(codigos)).group_by(
        Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal):
        ubicacion = ALMACEN if origen == 'INVAL' else (sucursal or 'Sin asignar')
        existencia, _ = resultado.setdefault(codigo, {}).get(ubicacion, (0, None))
        resultado[codigo][ubicacion] = (existencia + int(total or 0), float(precio) if precio else None)
    return resultado


@app.route('/api/inventario/stock', methods=['GET'])
def consultar_stock():
    """Existencias de artículos concretos por código o nombre (?q=), para consultar desde la tienda."""
    termino = texto(request.args.get('q'))
    if len(termino) < 2:
        return jsonify(success=False, error="Escribe al menos 2 caracteres del código o el nombre."), 400
    patron = f'%{termino.lower()}%'
    articulos = Articulo.query.filter(or_(
        func.lower(Articulo.codigo).like(patron), func.lower(Articulo.nombre).like(patron),
    )).order_by((Articulo.codigo == termino).desc(), Articulo.nombre).limit(20).all()
    codigos = [a.codigo for a in articulos]
    existencias = existencias_por_ubicacion(codigos)
    abc = casos_demanda.clasificacion_abc()
    pendientes = {(d.articulo_codigo, d.sucursal) for d in Discrepancia.query.filter(
        Discrepancia.articulo_codigo.in_(codigos), Discrepancia.estado == 'pendiente')}
    return jsonify(success=True, items=[{
        'codigo': a.codigo, 'nombre': a.nombre, 'grupo': a.nombredegrupo, 'clasificacion_abc': abc.get(a.codigo),
        'existencias': [{'ubicacion': u, 'existencia': n, 'precio_usd': precio, 'discrepancia_pendiente': (a.codigo, u) in pendientes}
                        for u, (n, precio) in sorted(existencias.get(a.codigo, {}).items(), key=lambda x: (x[0] != ALMACEN, x[0]))],
    } for a in articulos])


def serializar_discrepancia(d):
    return {
        'id': d.id, 'articulo_codigo': d.articulo_codigo, 'articulo_nombre': d.articulo_nombre, 'sucursal': d.sucursal,
        'existencia_sistema': d.existencia_sistema, 'existencia_contada': d.existencia_contada,
        'diferencia': d.existencia_contada - d.existencia_sistema, 'comentario': d.comentario, 'estado': d.estado,
        'resolucion': d.resolucion, 'creado_por': d.creado_por, 'creado_en': d.creado_en.isoformat(timespec='seconds'),
        'revisado_por': d.revisado_por, 'revisado_en': d.revisado_en.isoformat(timespec='seconds') if d.revisado_en else None,
    }


@app.route('/api/discrepancias', methods=['GET'])
def listar_discrepancias():
    q = Discrepancia.query
    for campo in ('estado', 'sucursal'):
        if request.args.get(campo):
            q = q.filter(getattr(Discrepancia, campo) == request.args[campo])
    return jsonify(success=True, discrepancias=[serializar_discrepancia(d) for d in
                                                q.order_by(Discrepancia.creado_en.desc()).limit(200)])


@app.route('/api/discrepancias', methods=['POST'])
def reportar_discrepancia():
    """{"articulo_codigo", "sucursal", "existencia_contada", "comentario"}; la existencia del sistema sale del inventario."""
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    try:
        codigo, sucursal = texto(datos.get('articulo_codigo')), texto(datos.get('sucursal'))
        art = db.session.get(Articulo, codigo) if codigo else None
        if art is None:
            raise ErrorDominio("El artículo no existe.")
        if not sucursal:
            raise ErrorDominio("Indica la ubicación donde se contó la mercancía.")
        contada = entero(datos.get('existencia_contada'), 'La cantidad contada', 0)
        sistema = inventario.stock_en(sucursal, codigo)
        if contada == sistema:
            raise ErrorDominio(f"Lo contado coincide con el sistema ({sistema} u): no hay discrepancia que reportar.")
        comentario = texto(datos.get('comentario'))
        if len(comentario) < 3:
            raise ErrorDominio("Describe brevemente la discrepancia.")
        if Discrepancia.query.filter_by(articulo_codigo=codigo, sucursal=sucursal, estado='pendiente').first():
            raise Conflicto("Ya hay una discrepancia pendiente de revisión para este artículo en esa ubicación.")
    except ErrorDominio as e:
        return jsonify(success=False, error=str(e)), estado_http(e)
    d = Discrepancia(articulo_codigo=codigo, articulo_nombre=art.nombre, sucursal=sucursal, existencia_sistema=sistema,
                     existencia_contada=contada, comentario=comentario, estado='pendiente', creado_por=usuario[0],
                     creado_en=datetime.now())
    db.session.add(d)
    db.session.commit()
    return jsonify(success=True, discrepancia=serializar_discrepancia(d)), 201


@app.route('/api/discrepancias/<int:id_>', methods=['PATCH'])
def revisar_discrepancia(id_):
    """{"resolucion": "..."}: la marca como revisada; solo una vez."""
    datos = request.get_json(silent=True) or {}
    d = db.session.get(Discrepancia, id_)
    if d is None:
        return jsonify(success=False, error="La discrepancia no existe."), 404
    if d.estado != 'pendiente':
        return jsonify(success=False, error="La discrepancia ya fue revisada.", discrepancia=serializar_discrepancia(d)), 409
    resolucion = texto(datos.get('resolucion'))
    if len(resolucion) < 3:
        return jsonify(success=False, error="Indica qué se hizo con la discrepancia."), 400
    d.estado, d.resolucion = 'revisada', resolucion
    d.revisado_por, d.revisado_en = usuario_actual()[0], datetime.now()
    db.session.commit()
    return jsonify(success=True, discrepancia=serializar_discrepancia(d))


# Errores HTTP también en JSON para que el frontend siempre pueda leer la respuesta.
@app.errorhandler(404)
def no_encontrado(_):
    return jsonify(success=False, error="Recurso no encontrado."), 404

@app.errorhandler(405)
def metodo_no_permitido(_):
    return jsonify(success=False, error="Método no permitido."), 405

@app.errorhandler(413)
def archivo_muy_grande(_):
    return jsonify(success=False, error="El archivo supera el límite de 25 MB."), 413


inventario = InventarioSQL()
repo_traslados = RepositorioTrasladosSQL()
casos_demanda = CasosDemanda(RepositorioDemandaSQL(), repo_traslados)
app.register_blueprint(blueprint_traslados(
    CasosTraslados(repo_traslados, inventario, casos_demanda.sugerencias_traslado, casos_demanda.clasificacion_abc)))
app.register_blueprint(blueprint_demanda(casos_demanda))
app.register_blueprint(blueprint_ventas(CasosVentas(RepositorioVentasSQL())))
app.register_blueprint(blueprint_importacion(CasosImportacion(RepositorioCargasSQL(), LectorPandas())))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrar_esquema()
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
