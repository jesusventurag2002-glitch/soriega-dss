import os
import re
from datetime import datetime

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)

# Conexión a PostgreSQL. Se puede sobrescribir con la variable de entorno DATABASE_URL.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql://usuario:password@localhost:5432/dss_inventario'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB por archivo
db = SQLAlchemy(app)

# Orígenes permitidos para el frontend React (Vite: 5173, CRA: 3000).
ORIGENES_FRONTEND = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
CORS(app, resources={r'/api/*': {'origins': ORIGENES_FRONTEND}})


# ==================== MODELOS DE BASE DE DATOS ====================
class Articulo(db.Model):
    __tablename__ = 'articulos'
    codigo = db.Column(db.String(50), primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    referencia = db.Column(db.String(100))
    marca = db.Column(db.String(100))
    nombredegrupo = db.Column(db.String(100), default="Sin Grupo")
    costoex = db.Column(db.Numeric(12, 4), default=0.0000)
    proveedor = db.Column(db.String(150), default="Proveedor General")

class Inventario(db.Model):
    __tablename__ = 'inventarios'
    id = db.Column(db.Integer, primary_key=True)
    articulo_codigo = db.Column(db.String(50))
    origen_inventario = db.Column(db.String(10)) # 'INV' o 'INVAL'
    existencia = db.Column(db.Integer, default=0)

class TasaInterna(db.Model):
    __tablename__ = 'tasas_internas'
    fecha = db.Column(db.Date, primary_key=True)
    tasa_paralelo = db.Column(db.Numeric(12, 4), nullable=False)

class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(50), nullable=False)
    articulo_codigo = db.Column(db.String(50))
    nombre_articulo = db.Column(db.String(255))
    grupo_venta = db.Column(db.String(100), default="Sin Grupo")
    cantidad_neta = db.Column(db.Integer, nullable=False)
    precio_fin_moneda_local = db.Column(db.Numeric(12, 4), nullable=False)
    factor_sistema = db.Column(db.Numeric(12, 4), nullable=False)
    factura_real_usd = db.Column(db.Numeric(12, 4), default=0.0000)
    costo_real_usd = db.Column(db.Numeric(12, 4), default=0.0000)
    utilidad_real_usd = db.Column(db.Numeric(12, 4), default=0.0000)
    fecha_emision = db.Column(db.Date, nullable=False)


# ==================== UTILIDADES DE PARSEO ====================
TIPOS_REPORTE = {'ventas', 'inv_fisico', 'inv_inval'}

# EXCLUSIÓN DE CLIENTES ESPECIALES (reposiciones internas y mermas)
CLIENTES_EXCLUIDOS = [
    "REPOSICION MARGARITA",
    "REPOSICION VALENCIA",
    "PLASTINET VALENCIA",
    "SAUL NORIEGA",
    "MERCANCIA DANADA",
    "MERCANCIA EXTRAVIADA",
]

# Al menos una columna de cada grupo debe existir en el archivo.
COLUMNAS_REQUERIDAS = {
    'ventas': [('codigo', 'cdg'), ('emision',)],
    'inventario': [('codigo', 'cdg', 'codigoart'), ('existencia',)],
}


class ErrorCarga(Exception):
    """Error atribuible al archivo o a los parámetros enviados (HTTP 400)."""


def texto(valor, defecto=''):
    if valor is None or pd.isna(valor):
        return defecto
    return str(valor).strip() or defecto


def numero(valor, defecto=0.0):
    try:
        n = float(str(valor).replace(',', '.'))
    except (TypeError, ValueError):
        return defecto
    return defecto if pd.isna(n) else n


def codigo_articulo(valor):
    # Excel suele entregar los códigos como float (12345.0)
    return texto(valor).split('.')[0].strip()


def parsear_fecha(valor):
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    partes = str(valor).split()
    if not partes:
        return None
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(partes[0], formato).date()
        except ValueError:
            continue
    return None


def leer_archivo(archivo, tipo_reporte):
    nombre = archivo.filename.lower()
    header = 1 if tipo_reporte == 'ventas' else 0
    if nombre.endswith('.csv'):
        df = pd.read_csv(archivo, header=header)
    elif nombre.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(archivo, header=header)
    else:
        raise ErrorCarga("Formato no soportado. Usa .xlsx, .xls o .csv.")

    if df.empty:
        raise ErrorCarga("Archivo vacío o no procesable.")

    df.columns = df.columns.astype(str).str.strip().str.lower()

    clave = 'ventas' if tipo_reporte == 'ventas' else 'inventario'
    faltantes = [' / '.join(g) for g in COLUMNAS_REQUERIDAS[clave] if not any(c in df.columns for c in g)]
    if faltantes:
        raise ErrorCarga(
            f"Faltan columnas requeridas: {', '.join(faltantes)}. "
            f"Columnas encontradas (fila {header + 1}): {', '.join(df.columns[:15])}"
        )
    return df


# ==================== PROCESAMIENTO DE CARGAS ====================
def cargar_ventas(df):
    # Sin commit intermedio: si algo falla, el rollback conserva las ventas previas.
    Venta.query.delete()

    tiene_fact = 'fact' in df.columns
    tiene_costo = 'costo' in df.columns
    ventas, excluidas, sin_fecha = [], 0, 0

    for row in df.to_dict('records'):
        codigo_art = codigo_articulo(row.get('codigo', row.get('cdg')))
        if not codigo_art or codigo_art == 'nan':
            continue

        cliente_nombre = texto(row.get('nombrecli')).upper()
        if any(excluido in cliente_nombre for excluido in CLIENTES_EXCLUIDOS):
            excluidas += 1
            continue

        fecha_emision = parsear_fecha(row.get('emision'))
        if fecha_emision is None:
            sin_fecha += 1
            continue

        grupo_venta = texto(row.get('nombredegr', row.get('nombredegrupo')), 'SIN GRUPO').upper()
        if grupo_venta in ["NAN", "NONE", "0"]:
            grupo_venta = "SIN GRUPO"

        f_sistema = numero(row.get('factor'), 1.0)
        if f_sistema <= 0:
            f_sistema = 1.0
        precio_local = numero(row.get('preciofin'))
        cantidad_neta = int(numero(row.get('cantidad'))) - int(numero(row.get('cntdevuelt')))

        # Facturación real: columna 'fact' del Excel; si no viene, fórmula equivalente (IVA 16%).
        if tiene_fact:
            factura_real = numero(row.get('fact'))
        else:
            factura_real = ((precio_local * 1.16) * cantidad_neta) / f_sistema

        if tiene_costo:
            costo_real = numero(row.get('costo'))
        else:
            costo_real = numero(row.get('costoex')) * cantidad_neta

        ventas.append(Venta(
            documento=texto(row.get('documento'), 'S/D'), articulo_codigo=codigo_art,
            nombre_articulo=texto(row.get('nombre'), 'Artículo'), grupo_venta=grupo_venta,
            cantidad_neta=cantidad_neta, precio_fin_moneda_local=precio_local,
            factor_sistema=f_sistema, factura_real_usd=factura_real,
            costo_real_usd=costo_real, utilidad_real_usd=factura_real - costo_real,
            fecha_emision=fecha_emision,
        ))

    db.session.add_all(ventas)
    db.session.commit()

    mensaje = f"Historial de ventas cargado: {len(ventas)} registros."
    if excluidas:
        mensaje += f" {excluidas} excluidos por cliente especial."
    if sin_fecha:
        mensaje += f" {sin_fecha} omitidos por fecha inválida."
    return mensaje


def cargar_inventario(df, origen):
    # Precarga en memoria para evitar una consulta por fila.
    articulos = {a.codigo: a for a in Articulo.query.all()}
    inventarios = {i.articulo_codigo: i for i in Inventario.query.filter_by(origen_inventario=origen)}
    nuevos, actualizados = 0, 0

    for row in df.to_dict('records'):
        codigo_art = codigo_articulo(row.get('codigo', row.get('cdg', row.get('codigoart'))))
        if not codigo_art or codigo_art == 'nan':
            continue

        existencia_actual = int(numero(row.get('existencia')))
        costo_val = numero(row.get('costoex', row.get('costo')))
        grupo_val = texto(row.get('nombredegr', row.get('nombredegrupo'))).upper()

        art = articulos.get(codigo_art)
        if not art:
            art = Articulo(
                codigo=codigo_art,
                nombre=texto(row.get('nombre', row.get('nombreart')), 'Sin Nombre'),
                nombredegrupo=grupo_val or 'SIN GRUPO',
                costoex=costo_val,
            )
            db.session.add(art)
            articulos[codigo_art] = art
            nuevos += 1
        else:
            art.costoex = costo_val
            if grupo_val:
                art.nombredegrupo = grupo_val
            actualizados += 1

        inv = inventarios.get(codigo_art)
        if inv:
            inv.existencia = existencia_actual
        else:
            inv = Inventario(articulo_codigo=codigo_art, origen_inventario=origen, existencia=existencia_actual)
            db.session.add(inv)
            inventarios[codigo_art] = inv

    db.session.commit()
    return (f"Inventario {origen} guardado: {nuevos + actualizados} artículos "
            f"({nuevos} nuevos, {actualizados} actualizados).")


# ==================== API ====================
@app.route('/api/carga_inicial', methods=['POST'])
def carga_inicial():
    tipo_reporte = request.form.get('tipo_reporte')
    archivo = request.files.get('archivo')

    if tipo_reporte not in TIPOS_REPORTE:
        return jsonify(success=False, error=f"tipo_reporte inválido. Opciones: {', '.join(sorted(TIPOS_REPORTE))}."), 400
    if not archivo or not archivo.filename:
        return jsonify(success=False, error="No se recibió ningún archivo."), 400

    try:
        df = leer_archivo(archivo, tipo_reporte)
        if tipo_reporte == 'ventas':
            mensaje = cargar_ventas(df)
        else:
            mensaje = cargar_inventario(df, 'INV' if tipo_reporte == 'inv_fisico' else 'INVAL')
        return jsonify(success=True, message=mensaje), 200
    except ErrorCarga as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 400
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Error procesando carga inicial")
        return jsonify(success=False, error=f"Error procesando el archivo: {e}"), 500


@app.route('/api/resumen', methods=['GET'])
def resumen():
    hoy = datetime.today()
    mes = request.args.get('mes', default=hoy.month, type=int)
    ano = request.args.get('ano', default=hoy.year, type=int)
    filtro = (
        func.extract('month', Venta.fecha_emision) == mes,
        func.extract('year', Venta.fecha_emision) == ano,
    )

    total_factura, total_costo = db.session.query(
        func.coalesce(func.sum(Venta.factura_real_usd), 0),
        func.coalesce(func.sum(Venta.costo_real_usd), 0),
    ).filter(*filtro).one()

    ventas_por_grupo = db.session.query(
        Venta.grupo_venta, func.sum(Venta.factura_real_usd)
    ).filter(*filtro).group_by(Venta.grupo_venta).order_by(func.sum(Venta.factura_real_usd).desc()).all()

    return jsonify(
        success=True,
        mes=mes,
        ano=ano,
        total_factura=round(float(total_factura), 2),
        total_costo=round(float(total_costo), 2),
        total_utilidad=round(float(total_factura) - float(total_costo), 2),
        ventas_por_grupo=[
            {'grupo': str(g).strip().upper() if g else "SIN GRUPO", 'total': round(float(t), 2)}
            for g, t in ventas_por_grupo
        ],
    )


@app.route('/api/logistica', methods=['POST'])
def logistica():
    datos = request.get_json(silent=True) or {}
    tipo_analisis = datos.get('tipo_analisis')
    if tipo_analisis not in ('traslado', 'reposicion'):
        return jsonify(success=False, error="tipo_analisis debe ser 'traslado' o 'reposicion'."), 400
    try:
        dias = int(datos.get('dias', 15))
    except (TypeError, ValueError):
        return jsonify(success=False, error="dias debe ser un número entero."), 400

    stock = {}
    for codigo, origen, total in db.session.query(
        Inventario.articulo_codigo, Inventario.origen_inventario, func.sum(Inventario.existencia)
    ).group_by(Inventario.articulo_codigo, Inventario.origen_inventario):
        stock[(codigo, origen)] = int(total or 0)

    ventas = {
        codigo: (int(unidades or 0), desde, hasta)
        for codigo, unidades, desde, hasta in db.session.query(
            Venta.articulo_codigo, func.sum(Venta.cantidad_neta),
            func.min(Venta.fecha_emision), func.max(Venta.fecha_emision),
        ).group_by(Venta.articulo_codigo)
    }

    resultados = []
    for art in Articulo.query.all():
        stock_inv = stock.get((art.codigo, 'INV'), 0)
        stock_inval = stock.get((art.codigo, 'INVAL'), 0)

        total_unidades, desde, hasta = ventas.get(art.codigo, (0, None, None))
        rango_dias = (hasta - desde).days + 1 if desde else 30
        vpd = total_unidades / (rango_dias if rango_dias > 0 else 1)
        demanda_proyectada = vpd * dias

        if tipo_analisis == 'traslado':
            if stock_inv < demanda_proyectada and stock_inval > 0:
                cant_a_mover = min(round(demanda_proyectada - stock_inv), stock_inval)
                if cant_a_mover > 0:
                    resultados.append({
                        'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                        'origen': 'INVAL', 'destino': 'INV', 'cantidad': cant_a_mover, 'disponible_almacen': stock_inval,
                    })
        else:
            stock_total = stock_inv + stock_inval
            if stock_total < demanda_proyectada:
                cant_a_pedir = max(0, round(demanda_proyectada - stock_total))
                if cant_a_pedir > 0:
                    resultados.append({
                        'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                        'proveedor': art.proveedor, 'cantidad_pedir': cant_a_pedir,
                        'deficit': round(demanda_proyectada - stock_total),
                    })

    return jsonify(success=True, tipo_analisis=tipo_analisis, dias=dias, resultados=resultados)


@app.route('/api/tasas', methods=['GET'])
def listar_tasas():
    tasas = TasaInterna.query.order_by(TasaInterna.fecha.desc()).limit(5).all()
    return jsonify(success=True, tasas=[
        {'fecha': t.fecha.isoformat(), 'tasa_paralelo': float(t.tasa_paralelo)} for t in tasas
    ])


@app.route('/api/tasas', methods=['POST'])
def guardar_tasas():
    """Recibe {"lista_tasas": "2026-10-01 36,50\n02/10/2026 36,75"} (una fecha y tasa por línea)."""
    datos = request.get_json(silent=True) or {}
    lista_tasas_raw = (datos.get('lista_tasas') or '').strip()
    if not lista_tasas_raw:
        return jsonify(success=False, error="No se recibieron tasas."), 400

    guardadas = 0
    try:
        for linea in lista_tasas_raw.splitlines():
            partes = re.split(r'[\t,\s]+', linea.strip(), maxsplit=1)
            if len(partes) < 2:
                continue
            fecha_obj = parsear_fecha(partes[0])
            tasa_val = numero(partes[1], None)
            if fecha_obj is None or tasa_val is None:
                continue
            tasa_existente = db.session.get(TasaInterna, fecha_obj)
            if tasa_existente:
                tasa_existente.tasa_paralelo = tasa_val
            else:
                db.session.add(TasaInterna(fecha=fecha_obj, tasa_paralelo=tasa_val))
            guardadas += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=f"Error guardando tasas: {e}"), 500

    return jsonify(success=True, message=f"Historial cambiario actualizado: {guardadas} tasas.")


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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=5000, debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
