"""Ruta HTTP de la carga inicial de reportes."""
from flask import Blueprint, current_app, jsonify, request

from adaptadores.entrada.http import estado_http, usuario_actual
from aplicacion.importacion import CasosImportacion
from dominio.errores import ErrorDominio


def crear_blueprint(casos: CasosImportacion):
    bp = Blueprint('importacion', __name__)

    @bp.post('/api/carga_inicial')
    def carga_inicial():
        archivo = request.files.get('archivo')
        try:
            mensaje = casos.cargar(request.form.get('tipo_reporte'), archivo.filename if archivo else None,
                                   archivo.read() if archivo and archivo.filename else b'', request.form.get('sucursal'),
                                   usuario_actual())
        except ErrorDominio as e:
            return jsonify(success=False, error=str(e)), estado_http(e)
        except Exception as e:
            current_app.logger.exception("Error procesando carga inicial")
            return jsonify(success=False, error=f"Error procesando el archivo: {e}"), 500
        return jsonify(success=True, message=mensaje), 200

    return bp
