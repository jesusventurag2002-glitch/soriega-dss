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
from adaptadores.entrada.operacion import crear_blueprint as blueprint_operacion
from adaptadores.entrada.importacion import crear_blueprint as blueprint_importacion
from adaptadores.entrada.traslados import crear_blueprint as blueprint_traslados, resumen_documento, serializar_evento
from adaptadores.salida.migraciones import agrupar_traslados_en_documentos, migrar_esquema  # noqa: F401 (pruebas)
from adaptadores.salida.lector_pandas import LectorPandas
from adaptadores.salida.repo_cargas import RepositorioCargasSQL
from adaptadores.salida.repo_operacion import RepositorioAccionesSQL, RepositorioTableroSQL, RepositorioTiendaSQL
from adaptadores.salida.repo_demanda import RepositorioDemandaSQL
from adaptadores.salida.repo_inventario import InventarioSQL
from adaptadores.salida.repo_ventas import RepositorioVentasSQL
from adaptadores.salida.repo_traslados import ORDENES, RepositorioTrasladosSQL
from aplicacion.demanda import CasosDemanda
from aplicacion.importacion import CasosImportacion
from aplicacion.operacion import CasosEstancado, CasosTablero, CasosTienda
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
acciones = RepositorioAccionesSQL()
app.register_blueprint(blueprint_operacion(
    CasosEstancado(acciones, casos_demanda, repo_traslados, inventario),
    CasosTienda(RepositorioTiendaSQL(), inventario, casos_demanda),
    CasosTablero(RepositorioTableroSQL(), casos_demanda, acciones, inventario),
))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrar_esquema()
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
