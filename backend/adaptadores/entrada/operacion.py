"""Rutas HTTP de la operación diaria: capital estancado y su seguimiento, piso de venta, tablero e importaciones."""
from flask import Blueprint, jsonify, request

from adaptadores.entrada.http import estado_http, usuario_actual
from adaptadores.entrada.traslados import resumen_documento, serializar_evento
from aplicacion.operacion import CasosEstancado, CasosTablero, CasosTienda
from dominio.comun import texto
from dominio.errores import Conflicto, ErrorDominio
from dominio.estancado import TIPOS_ACCION_ESTANCADO


def serializar_accion(a):
    return {
        'id': a.id, 'articulo_codigo': a.articulo_codigo, 'articulo_nombre': a.articulo_nombre, 'tipo': a.tipo,
        'tipo_etiqueta': TIPOS_ACCION_ESTANCADO[a.tipo], 'estado': a.estado,
        'capital_al_registrar': float(a.capital_al_registrar) if a.capital_al_registrar is not None else None,
        'comentario': a.comentario, 'resultado': a.resultado, 'creado_por': a.creado_por,
        'creado_en': a.creado_en.isoformat(timespec='seconds'), 'cerrado_por': a.cerrado_por,
        'cerrado_en': a.cerrado_en.isoformat(timespec='seconds') if a.cerrado_en else None,
    }


def serializar_discrepancia(d):
    return {
        'id': d.id, 'articulo_codigo': d.articulo_codigo, 'articulo_nombre': d.articulo_nombre, 'sucursal': d.sucursal,
        'existencia_sistema': d.existencia_sistema, 'existencia_contada': d.existencia_contada,
        'diferencia': d.existencia_contada - d.existencia_sistema, 'comentario': d.comentario, 'estado': d.estado,
        'resolucion': d.resolucion, 'creado_por': d.creado_por, 'creado_en': d.creado_en.isoformat(timespec='seconds'),
        'revisado_por': d.revisado_por, 'revisado_en': d.revisado_en.isoformat(timespec='seconds') if d.revisado_en else None,
    }


def serializar_importacion(i):
    return {'id': i.id, 'tipo_reporte': i.tipo_reporte, 'sucursal': i.sucursal, 'archivo': i.archivo, 'exito': i.exito,
            'mensaje': i.mensaje, 'fecha_importacion': i.fecha_importacion.isoformat(timespec='seconds'),
            'datos_hasta': i.datos_hasta.isoformat() if i.datos_hasta else None, 'usuario': i.usuario}


def error(e, **extra):
    return jsonify(success=False, error=str(e), **extra), estado_http(e)


def crear_blueprint(estancado: CasosEstancado, tienda: CasosTienda, tablero: CasosTablero):
    bp = Blueprint('operacion', __name__)

    @bp.get('/api/capital_estancado')
    def capital_estancado():
        try:
            datos = estancado.capital_estancado(request.args.get('dias_min', default=90, type=int),
                                                request.args.get('limite', default=100, type=int),
                                                texto(request.args.get('sucursal')) or None)
        except ErrorDominio as e:
            return error(e)
        for a in datos['articulos']:
            a['acciones'] = [serializar_accion(x) for x in a['acciones']]
        return jsonify(success=True, **datos)

    @bp.get('/api/estancado/acciones')
    def listar_acciones_estancado():
        return jsonify(success=True, acciones=[serializar_accion(a) for a in
                                               estancado.listar(request.args.get('estado'), request.args.get('tipo'))])

    @bp.post('/api/estancado/acciones')
    def registrar_accion_estancado():
        try:
            accion = estancado.registrar(request.get_json(silent=True) or {}, usuario_actual())
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, accion=serializar_accion(accion)), 201

    @bp.patch('/api/estancado/acciones/<int:id_>')
    def cerrar_accion_estancado(id_):
        accion = None
        try:
            accion = estancado.obtener(id_)
            estancado.cerrar(accion, request.get_json(silent=True) or {}, usuario_actual())
        except Conflicto as e:
            return error(e, accion=serializar_accion(accion))
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, accion=serializar_accion(accion))

    @bp.get('/api/inventario/stock')
    def consultar_stock():
        try:
            items = tienda.consultar_stock(request.args.get('q'))
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, items=[{
            'codigo': a.codigo, 'nombre': a.nombre, 'grupo': a.nombredegrupo, 'clasificacion_abc': abc,
            'existencias': [{'ubicacion': u, 'existencia': n, 'precio_usd': p, 'discrepancia_pendiente': pendiente}
                            for u, n, p, pendiente in existencias],
        } for a, abc, existencias in items])

    @bp.get('/api/discrepancias')
    def listar_discrepancias():
        return jsonify(success=True, discrepancias=[serializar_discrepancia(d) for d in tienda.listar_discrepancias(
            request.args.get('estado'), request.args.get('sucursal'))])

    @bp.post('/api/discrepancias')
    def reportar_discrepancia():
        try:
            d = tienda.reportar_discrepancia(request.get_json(silent=True) or {}, usuario_actual())
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, discrepancia=serializar_discrepancia(d)), 201

    @bp.patch('/api/discrepancias/<int:id_>')
    def revisar_discrepancia(id_):
        d = None
        try:
            d = tienda.obtener_discrepancia(id_)
            tienda.revisar_discrepancia(d, request.get_json(silent=True) or {}, usuario_actual())
        except Conflicto as e:
            return error(e, discrepancia=serializar_discrepancia(d))
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, discrepancia=serializar_discrepancia(d))

    @bp.get('/api/dashboard')
    def dashboard():
        datos = tablero.tablero(texto(request.args.get('sucursal')) or None)
        datos['pendientes'] = {k: [resumen_documento(d) for d in v] for k, v in datos['pendientes'].items()}
        datos['acciones_estancado']['items'] = [serializar_accion(a) for a in datos['acciones_estancado']['items']]
        datos['actividad'] = [{**serializar_evento(e), 'traslado': resumen_documento(d)} for e, d in datos['actividad']]
        datos['importaciones'] = [serializar_importacion(i) for i in datos['importaciones']]
        return jsonify(success=True, **datos)

    @bp.get('/api/importaciones')
    def listar_importaciones():
        return jsonify(success=True, importaciones=[serializar_importacion(i) for i in tablero.importaciones()])

    return bp
