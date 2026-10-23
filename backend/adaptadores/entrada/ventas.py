"""Rutas HTTP de ventas, excepciones y tasas."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from adaptadores.entrada.http import estado_http
from aplicacion.ventas import CasosVentas
from dominio.comun import parsear_fecha
from dominio.errores import ErrorDominio


def crear_blueprint(casos: CasosVentas):
    bp = Blueprint('ventas', __name__)

    @bp.get('/api/resumen')
    def resumen():
        hoy = datetime.today()
        mes = request.args.get('mes', default=hoy.month, type=int)
        ano = request.args.get('ano', default=hoy.year, type=int)
        return jsonify(success=True, **casos.resumen(mes, ano, request.args.get('excluir')))

    @bp.put('/api/excepciones')
    def guardar_excepciones():
        try:
            excluidas = casos.guardar_excepciones(request.get_json(silent=True) or {})
        except ErrorDominio as e:
            return jsonify(success=False, error=str(e)), estado_http(e)
        return jsonify(success=True, excluidas=excluidas)

    @bp.get('/api/ventas/analisis')
    def analisis_ventas():
        try:
            datos = casos.analisis(request.args.get('mes', type=int), request.args.get('ano', type=int),
                                   request.args.get('excluir'))
        except ErrorDominio as e:
            return jsonify(success=False, error=str(e)), estado_http(e)
        return jsonify(success=True, **datos)

    @bp.get('/api/tasas')
    def listar_tasas():
        """Tasas BCV e interna vigentes en ?fecha= (por defecto hoy) y el historial de los ?dias= anteriores."""
        fecha = parsear_fecha(request.args.get('fecha')) or datetime.today().date()
        return jsonify(success=True, **casos.tasas(fecha, request.args.get('dias', default=30, type=int)))

    @bp.post('/api/tasas')
    def guardar_tasas():
        """Recibe {"lista_tasas": "2026-10-01 36,50\\n02/10/2026 36,75"} (una fecha y tasa por línea)."""
        lista = ((request.get_json(silent=True) or {}).get('lista_tasas') or '').strip()
        if not lista:
            return jsonify(success=False, error="No se recibieron tasas."), 400
        try:
            guardadas = casos.guardar_tasas(lista)
        except Exception as e:
            casos.revertir()
            return jsonify(success=False, error=f"Error guardando tasas: {e}"), 500
        return jsonify(success=True, message=f"Historial cambiario actualizado: {guardadas} tasas.")

    return bp
