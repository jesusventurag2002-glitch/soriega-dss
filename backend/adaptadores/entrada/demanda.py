"""Rutas HTTP de logística (sugerencias de traslado y compra) y productos críticos."""
from flask import Blueprint, jsonify, request

from aplicacion.demanda import CasosDemanda
from dominio.comun import texto
from dominio.demanda import DIAS_COBERTURA_CRITICA


def crear_blueprint(casos: CasosDemanda):
    bp = Blueprint('demanda', __name__)

    @bp.post('/api/logistica')
    def logistica():
        datos = request.get_json(silent=True) or {}
        tipo_analisis = datos.get('tipo_analisis')
        if tipo_analisis not in ('traslado', 'reposicion'):
            return jsonify(success=False, error="tipo_analisis debe ser 'traslado' o 'reposicion'."), 400
        try:
            dias = int(datos.get('dias', 15))
        except (TypeError, ValueError):
            return jsonify(success=False, error="dias debe ser un número entero."), 400
        resultados = casos.sugerencias_traslado(dias) if tipo_analisis == 'traslado' else casos.reposicion(dias)
        return jsonify(success=True, tipo_analisis=tipo_analisis, dias=dias, resultados=resultados)

    @bp.get('/api/inventario/criticos')
    def listar_criticos():
        sucursal = texto(request.args.get('sucursal')) or None
        dias = request.args.get('dias', default=DIAS_COBERTURA_CRITICA, type=int)
        return jsonify(success=True, dias_cobertura=dias, items=casos.productos_criticos(sucursal, dias))

    return bp
