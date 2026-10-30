"""Composición de la aplicación: crea Flask, instancia los adaptadores e inyecta los casos de uso en las rutas.

Capas: dominio/ (reglas puras) <- aplicacion/ (casos de uso) -> puertos/ (interfaces) <- adaptadores/ (Flask,
SQLAlchemy, pandas). Este archivo es el único que conoce todas las piezas.
"""
import os

from flask import Flask, jsonify
from flask_cors import CORS

from adaptadores.entrada.demanda import crear_blueprint as blueprint_demanda
from adaptadores.entrada.importacion import crear_blueprint as blueprint_importacion
from adaptadores.entrada.operacion import crear_blueprint as blueprint_operacion
from adaptadores.entrada.traslados import crear_blueprint as blueprint_traslados
from adaptadores.entrada.ventas import crear_blueprint as blueprint_ventas
from adaptadores.salida.lector_pandas import LectorPandas
from adaptadores.salida.migraciones import migrar_esquema
from adaptadores.salida.repo_cargas import RepositorioCargasSQL
from adaptadores.salida.repo_demanda import RepositorioDemandaSQL
from adaptadores.salida.repo_inventario import InventarioSQL
from adaptadores.salida.repo_operacion import RepositorioAccionesSQL, RepositorioTableroSQL, RepositorioTiendaSQL
from adaptadores.salida.repo_traslados import RepositorioTrasladosSQL
from adaptadores.salida.repo_ventas import RepositorioVentasSQL
from aplicacion.demanda import CasosDemanda
from aplicacion.importacion import CasosImportacion
from aplicacion.operacion import CasosEstancado, CasosTablero, CasosTienda
from aplicacion.traslados import CasosTraslados
from aplicacion.ventas import CasosVentas
# Las pruebas de integración preparan datos con los modelos y la migración a través de este módulo.
from adaptadores.salida.migraciones import agrupar_traslados_en_documentos  # noqa: F401
from adaptadores.salida.modelos import Articulo, EventoTraslado, Inventario, TasaInterna, Traslado, Venta, db  # noqa: F401

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


# Adaptadores de salida (no guardan estado: usan la sesión de Flask-SQLAlchemy de cada petición).
inventario = InventarioSQL()
traslados = RepositorioTrasladosSQL()
acciones = RepositorioAccionesSQL()

# Casos de uso y rutas.
demanda = CasosDemanda(RepositorioDemandaSQL(), traslados)
app.register_blueprint(blueprint_traslados(
    CasosTraslados(traslados, inventario, demanda.sugerencias_traslado, demanda.clasificacion_abc)))
app.register_blueprint(blueprint_demanda(demanda))
app.register_blueprint(blueprint_ventas(CasosVentas(RepositorioVentasSQL())))
app.register_blueprint(blueprint_importacion(CasosImportacion(RepositorioCargasSQL(), LectorPandas())))
app.register_blueprint(blueprint_operacion(
    CasosEstancado(acciones, demanda, traslados, inventario),
    CasosTienda(RepositorioTiendaSQL(), inventario, demanda),
    CasosTablero(RepositorioTableroSQL(), demanda, acciones, inventario),
))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrar_esquema()
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
