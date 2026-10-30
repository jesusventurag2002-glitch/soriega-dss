"""Rutas HTTP de traslados y su formato JSON."""
import io
import json

import pandas as pd
from flask import Blueprint, jsonify, request, send_file

from adaptadores.entrada.http import estado_http, usuario_actual
from aplicacion.traslados import CasosTraslados
from dominio import traslados as dom
from dominio.errores import Conflicto, ErrorDominio


def serializar_evento(e):
    return {
        'id': e.id, 'tipo': e.tipo, 'estado_anterior': e.estado_anterior, 'estado_nuevo': e.estado_nuevo,
        'usuario': e.usuario, 'rol': e.rol, 'fecha': e.fecha.isoformat(timespec='seconds'),
        'detalle': json.loads(e.detalle) if e.detalle else {},
    }


def serializar_linea(t):
    return {
        'id': t.id, 'articulo_codigo': t.articulo_codigo, 'articulo_nombre': t.articulo_nombre,
        'clasificacion_abc': t.clasificacion_abc, 'cantidad_sugerida': t.cantidad_sugerida,
        'cantidad_aprobada': t.cantidad_aprobada, 'cantidad_despachada': t.cantidad_despachada,
        'cantidad_recibida': t.cantidad_recibida, 'diferencia': dom.diferencia_de(t),
        'stock_origen': t.stock_origen, 'stock_destino': t.stock_destino, 'cobertura_dias': t.cobertura_dias,
    }


def resumen_documento(d):
    """Datos de un documento para listas: ruta, estado y totales de sus artículos."""
    lineas = sorted(dom.lineas_vigentes(d), key=dom.prioridad_linea)
    abc = {c: sum(1 for l in lineas if l.clasificacion_abc == c) for c in 'ABC'}
    return {
        'id': d.id, 'folio': dom.folio(d), 'tipo': d.tipo, 'origen': d.origen, 'destino': d.destino, 'estado': d.estado,
        'estado_etiqueta': dom.ESTADOS_TRASLADO[d.estado], 'total_articulos': len(lineas),
        'total_unidades': sum(dom.cantidad_vigente(l) for l in lineas), 'abc': abc,
        'clasificacion_abc': next((c for c in 'ABC' if abc[c]), None),
        'con_diferencias': sum(1 for l in lineas if dom.diferencia_de(l)),
        'articulos': [l.articulo_nombre for l in lineas[:3]],
        'actualizado_en': d.actualizado_en.isoformat(timespec='seconds'),
    }


def serializar_documento(d, rol=None, eventos=None):
    """Con `eventos` (el historial) incluye también las líneas: es la vista de detalle."""
    datos = {
        **resumen_documento(d),
        'horizonte_dias': d.horizonte_dias, 'motivo_rechazo': d.motivo_rechazo, 'observaciones': d.observaciones,
        'creado_por': d.creado_por, 'creado_en': d.creado_en.isoformat(timespec='seconds'), 'version': d.version,
        'acciones': dom.acciones_disponibles(d, rol), 'editable': d.estado == 'borrador',
        'retirable': dom.puede_retirar(d, rol),
    }
    if eventos is not None:
        datos['lineas'] = [serializar_linea(l) for l in sorted(dom.lineas_vigentes(d), key=dom.prioridad_linea)]
        datos['eventos'] = [serializar_evento(e) for e in eventos]
    return datos


def crear_blueprint(casos: CasosTraslados):
    bp = Blueprint('traslados', __name__)

    def detalle(d, rol):
        return serializar_documento(d, rol, casos.eventos(d))

    def error(e, d=None):
        cuerpo = {'success': False, 'error': str(e)}
        if d is not None and isinstance(e, Conflicto):
            # El cliente recibe el estado real para no mostrar algo que contradiga al servidor.
            cuerpo['traslado'] = detalle(casos.recargar(d), usuario_actual()[1])
        else:
            casos.revertir()
        return jsonify(cuerpo), estado_http(e)

    def sobre_documento(id_, operacion):
        """Ejecuta operacion(usuario) y responde con el detalle; en un conflicto devuelve el documento vigente."""
        usuario = usuario_actual()
        try:
            d = casos.obtener(id_)
        except ErrorDominio as e:
            return error(e)
        try:
            d = operacion(usuario)
        except ErrorDominio as e:
            return error(e, d)
        return jsonify(success=True, traslado=detalle(d, usuario[1]))

    @bp.get('/api/traslados')
    def listar_traslados():
        """Bandeja de documentos de traslado con filtros, orden y paginación; conteos por pestaña con los mismos filtros."""
        rol = usuario_actual()[1]
        try:
            r = casos.bandeja(request.args.to_dict(), request.args.get('grupo', 'activos'),
                              request.args.get('orden', 'prioridad'), request.args.get('pagina', default=1, type=int),
                              request.args.get('por_pagina', default=25, type=int))
        except ErrorDominio as e:
            return jsonify(success=False, error=str(e)), estado_http(e)
        return jsonify(success=True, **{**r, 'items': [serializar_documento(d, rol) for d in r['items']]})

    @bp.get('/api/traslados/<int:id_>')
    def detalle_traslado(id_):
        try:
            d = casos.obtener(id_)
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, traslado=detalle(d, usuario_actual()[1]))

    @bp.get('/api/traslados/<int:id_>/excel')
    def exportar_traslado(id_):
        try:
            nombre, filas = casos.exportacion(id_)
        except ErrorDominio as e:
            return jsonify(success=False, error=str(e)), estado_http(e)
        archivo = io.BytesIO()
        pd.DataFrame(filas, columns=['Código', 'Descripción', 'Cantidad', 'Costo (sin IVA)', 'Costo x tasa interna'])             .to_excel(archivo, index=False)
        archivo.seek(0)
        return send_file(archivo, as_attachment=True, download_name=nombre,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @bp.patch('/api/traslados/<int:id_>')
    def editar_traslado(id_):
        """{"version": 3, "lineas": [{"id": 8, "cantidad_sugerida": 20}], "observaciones": "..."}"""
        datos = request.get_json(silent=True) or {}
        return sobre_documento(id_, lambda u: casos.editar(id_, datos, u))

    @bp.delete('/api/traslados/<int:id_>/lineas/<int:linea_id>')
    def retirar_articulo(id_, linea_id):
        datos = request.get_json(silent=True) or {}
        return sobre_documento(id_, lambda u: casos.retirar(id_, linea_id, datos, u))

    @bp.post('/api/traslados/<int:id_>/acciones')
    def accion_traslado(id_):
        """{"accion": "aprobar", "version": 3, "cantidades": {"8": 10}, "motivo": "...", "comentario": "..."}"""
        datos = request.get_json(silent=True) or {}
        return sobre_documento(id_, lambda u: casos.accionar(id_, datos, u))

    @bp.post('/api/traslados/lote')
    def accion_lote():
        """{"accion": "enviar", "items": [{"id": 1, "version": 2}, ...]}: todo o nada."""
        datos = request.get_json(silent=True) or {}
        usuario = usuario_actual()
        items = datos.get('items') or []
        try:
            procesados, errores = casos.lote(datos.get('accion'), items, usuario)
        except ErrorDominio as e:
            return jsonify(success=False, error=str(e)), estado_http(e)
        if errores:
            return jsonify(success=False, error=f"No se aplicó ningún cambio: {len(errores)} de {len(items)} traslados no lo permiten.",
                           errores=errores), 409
        return jsonify(success=True, traslados=[serializar_documento(d, usuario[1]) for d in procesados])

    @bp.post('/api/traslados/generar')
    def generar_traslados():
        """{"dias": 15, "clases": ["A"]}: sin clases se proponen artículos de todas las clases ABC."""
        try:
            r = casos.generar(request.get_json(silent=True) or {}, usuario_actual())
        except ErrorDominio as e:
            return error(e)
        clases, documentos, omitidos = r['clases'], r['documentos'], r['omitidos']
        return jsonify(success=True, creados=r['creados'], documentos=documentos, omitidos=omitidos,
                       sugerencias=r['sugerencias'],
                       message=(f"Se agregaron {r['creados']} artículos ({'clase' if len(clases) == 1 else 'clases'} "
                                f"{', '.join(sorted(clases))}) en {documentos} "
                                f"{'documento' if documentos == 1 else 'documentos'} de traslado." +
                                (f" {omitidos} sugerencias ya tenían un traslado abierto." if omitidos else "")))

    @bp.post('/api/traslados')
    def crear_retorno():
        """Retorno de mercancía de una sucursal al almacén principal (p. ej. mercancía estancada)."""
        usuario = usuario_actual()
        try:
            d = casos.crear_retorno(request.get_json(silent=True) or {}, usuario)
        except ErrorDominio as e:
            return error(e)
        return jsonify(success=True, traslado=detalle(d, usuario[1])), 201

    return bp
