import io
import os
import re
import unicodedata
from datetime import datetime, timedelta

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, case, func, inspect, or_, text, true

app = Flask(__name__)

# Conexión a PostgreSQL. Se puede sobrescribir con la variable de entorno DATABASE_URL.
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql+psycopg://usuario:password@localhost:5432/dss_inventario'
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
    origen_inventario = db.Column(db.String(10)) # 'INV' (sucursales) o 'INVAL' (almacén principal)
    existencia = db.Column(db.Integer, default=0)
    sucursal = db.Column(db.String(100))  # solo para 'INV'; el almacén principal no tiene sucursal

class TasaInterna(db.Model):
    __tablename__ = 'tasas_internas'
    fecha = db.Column(db.Date, primary_key=True)
    tasa_paralelo = db.Column(db.Numeric(12, 4))  # tasa interna del día (hoja TASA / sistema)
    tasa_bcv = db.Column(db.Numeric(12, 4))  # tasa BCV del día (FACTOR del reporte de ventas)

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
    sucursal = db.Column(db.String(100))  # indicada al cargar el reporte; el archivo no la trae
    factura_bs = db.Column(db.Numeric(16, 4))  # PRECIOFIN * 1.16 * cantidad neta; el USD se calcula con la tasa interna
    excepcion = db.Column(db.String(50))  # id de EXCEPCIONES si no es facturación comercial


# ==================== UTILIDADES DE PARSEO ====================
TIPOS_REPORTE = {'ventas', 'inv_fisico', 'inv_inval', 'tasas'}

# Excepciones de la hoja ANAL: ventas que no son facturación comercial (reposiciones entre tiendas,
# mermas, consumo interno y servicios). Se guardan marcadas y cada consulta decide si excluirlas.
# Se comparan por igualdad exacta (como SUMIFS) contra el campo indicado del reporte.
EXCEPCIONES = [
    {'id': 'plastinet_valencia', 'nombre': 'Plastinet Valencia', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'PLASTINET VALENCIA'},
    {'id': 'reposicion_maturin', 'nombre': 'Reposición Maturín', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'REPOSICION MATURIN'},
    {'id': 'reposicion_margarita', 'nombre': 'Reposición Margarita', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'REPOSICION MARGARITA'},
    {'id': 'saul_noriega', 'nombre': 'Saúl Noriega', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'SAUL NORIEGA'},
    {'id': 'brotcars', 'nombre': 'Brotcars', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'BROTCARS'},
    {'id': 'mercancia_danada', 'nombre': 'Mercancía dañada', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'MERCANCIA DANADA'},
    {'id': 'productos_oficina', 'nombre': 'Productos para oficina', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'PRODUCTOS PARA OFICINA'},
    {'id': 'servicio_brotcarservice', 'nombre': 'Brotcarservice', 'categoria': 'servicio', 'campo': 'nombredegr', 'valor': 'BROTCARSERVICE'},
    {'id': 'servicio_balloonazo', 'nombre': 'Arreglos Balloonazo (mano de obra)', 'categoria': 'servicio', 'campo': 'nombre', 'valor': 'ARREGLOS BALLOONAZO MANO DE OBRA'},
    # No figura en ANAL; el backend la excluía antes, por eso se ofrece desmarcada.
    {'id': 'mercancia_extraviada', 'nombre': 'Mercancía extraviada', 'categoria': 'cliente', 'campo': 'nombrecli', 'valor': 'MERCANCIA EXTRAVIADA', 'por_defecto': False},
]
EXCEPCIONES_POR_DEFECTO = [e['id'] for e in EXCEPCIONES if e.get('por_defecto', True)]

# Artículos de uso interno (no comerciales): se ignoran en toda la lógica de negocio.
GRUPOS_EXCLUIDOS = ["MARKETING"]
SUBGRUPOS_EXCLUIDOS = ["EQUIPOS DE OFICINA"]

# Al menos una columna de cada grupo debe existir en el archivo.
COLUMNAS_REQUERIDAS = {
    'ventas': [('codigo', 'cdg'), ('emision',)],
    'inventario': [('codigo', 'cdg', 'codigoart'), ('existencia',)],
    'tasas': [('fecha',), ('tasa',)],
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


MAX_FILAS_TITULO = 5  # filas de título que puede traer el reporte antes de los encabezados


def normalizar_columnas(columnas):
    return pd.Index(columnas).astype(str).str.strip().str.lower()


def es_articulo_excluido(row):
    grupo = texto(row.get('nombredegr', row.get('nombredegrupo'))).upper()
    subgrupo = texto(row.get('nombre_sub')).upper()
    return grupo in GRUPOS_EXCLUIDOS or subgrupo in SUBGRUPOS_EXCLUIDOS


def detectar_excepcion(row):
    valores = {
        'nombrecli': texto(row.get('nombrecli')).upper(),
        'nombredegr': texto(row.get('nombredegr', row.get('nombredegrupo'))).upper(),
        'nombre': texto(row.get('nombre')).upper(),
    }
    return next((e['id'] for e in EXCEPCIONES if valores[e['campo']] == e['valor']), None)


def leer_archivo(archivo, tipo_reporte):
    nombre = archivo.filename.lower()
    contenido = io.BytesIO(archivo.read())

    if nombre.endswith('.csv'):
        def leer(**kwargs):
            contenido.seek(0)
            try:
                return pd.read_csv(contenido, **kwargs)
            except UnicodeDecodeError:
                contenido.seek(0)
                return pd.read_csv(contenido, encoding='latin-1', **kwargs)
    elif nombre.endswith(('.xlsx', '.xls')):
        # El sistema administrativo exporta .XLS que en realidad son .xlsx;
        # pandas detecta el formato real por el contenido, no por la extensión.
        libro = pd.ExcelFile(contenido)
        # Las tasas pueden venir en el libro de pedidos completo: se usa su hoja TASA.
        hoja = next((h for h in libro.sheet_names if h.strip().upper() == 'TASA'), 0) if tipo_reporte == 'tasas' else 0

        def leer(**kwargs):
            return libro.parse(sheet_name=hoja, **kwargs)
    else:
        raise ErrorCarga("Formato no soportado. Usa .xlsx, .xls o .csv.")

    # Los reportes traen un título antes de los encabezados ("Lista De Inventario...",
    # "Artículos Vendidos..."), así que se busca la fila que contiene las columnas requeridas.
    clave = tipo_reporte if tipo_reporte in COLUMNAS_REQUERIDAS else 'inventario'
    requeridas = COLUMNAS_REQUERIDAS[clave]
    for header in range(MAX_FILAS_TITULO + 1):
        columnas = normalizar_columnas(leer(header=header, nrows=0).columns)
        if all(any(c in columnas for c in grupo) for grupo in requeridas):
            break
    else:
        faltantes = ', '.join(' / '.join(g) for g in requeridas)
        raise ErrorCarga(
            f"No se encontraron las columnas requeridas ({faltantes}) en las primeras "
            f"{MAX_FILAS_TITULO + 1} filas. Verifica que el archivo corresponda al tipo de reporte seleccionado."
        )

    df = leer(header=header)
    if df.empty:
        raise ErrorCarga("Archivo vacío o no procesable.")
    df.columns = normalizar_columnas(df.columns)
    return df


# ==================== PROCESAMIENTO DE CARGAS ====================
def cargar_ventas(df, sucursal):
    # Reemplaza solo las ventas de esta sucursal (y las de cargas antiguas sin sucursal).
    # Sin commit intermedio: si algo falla, el rollback conserva las ventas previas.
    Venta.query.filter(or_(Venta.sucursal == sucursal, Venta.sucursal.is_(None))).delete(synchronize_session=False)

    tiene_fact = 'fact' in df.columns
    tiene_costo = 'costo' in df.columns
    ventas, internas, sin_fecha = [], 0, 0
    por_excepcion = {}
    tasas_bcv = {}  # FACTOR del reporte = tasa BCV del día

    for row in df.to_dict('records'):
        codigo_art = codigo_articulo(row.get('codigo', row.get('cdg')))
        if not codigo_art or codigo_art == 'nan':
            continue

        if es_articulo_excluido(row):
            internas += 1
            continue

        excepcion = detectar_excepcion(row)
        if excepcion:
            por_excepcion[excepcion] = por_excepcion.get(excepcion, 0) + 1

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
        elif f_sistema > 1:
            tasas_bcv.setdefault(fecha_emision, f_sistema)
        precio_local = numero(row.get('preciofin'))
        cantidad_neta = int(numero(row.get('cantidad'))) - int(numero(row.get('cntdevuelt')))

        # Facturación (hoja VENTA): PRECIOFIN * 1.16 * cantidad neta, en Bs. El USD se obtiene al consultar
        # dividiendo entre la tasa interna del día; factura_real_usd (con FACTOR) queda como respaldo
        # para fechas sin tasa interna. Si el archivo ya trae la columna 'fact', se usa tal cual.
        if tiene_fact:
            factura_bs = None
            factura_real = numero(row.get('fact'))
        else:
            factura_bs = (precio_local * 1.16) * cantidad_neta
            factura_real = factura_bs / f_sistema

        if tiene_costo:
            costo_real = numero(row.get('costo'))
        else:
            costo_real = (numero(row.get('costoex')) * 1.16) * cantidad_neta

        ventas.append(Venta(
            documento=texto(row.get('documento'), 'S/D'), articulo_codigo=codigo_art,
            nombre_articulo=texto(row.get('nombre'), 'Artículo'), grupo_venta=grupo_venta,
            cantidad_neta=cantidad_neta, precio_fin_moneda_local=precio_local,
            factor_sistema=f_sistema, factura_real_usd=factura_real,
            costo_real_usd=costo_real, utilidad_real_usd=factura_real - costo_real,
            fecha_emision=fecha_emision, sucursal=sucursal,
            factura_bs=factura_bs, excepcion=excepcion,
        ))

    db.session.add_all(ventas)
    registrar_tasas(tasas_bcv, 'tasa_bcv')
    db.session.commit()

    mensaje = f"Historial de ventas de {sucursal} cargado: {len(ventas)} registros."
    if por_excepcion:
        nombres = {e['id']: e['nombre'] for e in EXCEPCIONES}
        mensaje += (f" {sum(por_excepcion.values())} marcados como excepción y excluibles en el análisis ("
                    + ', '.join(f"{nombres[k]}: {n}" for k, n in sorted(por_excepcion.items(), key=lambda x: -x[1])) + ").")
    if tasas_bcv:
        mensaje += f" Tasa BCV registrada para {len(tasas_bcv)} días."
    if internas:
        mensaje += f" {internas} ignorados por ser de uso interno (Marketing / Equipos de oficina)."
    if sin_fecha:
        mensaje += f" {sin_fecha} omitidos por fecha inválida."
    return mensaje


def registrar_tasas(por_fecha, campo):
    """Inserta o actualiza una de las tasas ('tasa_paralelo' o 'tasa_bcv') por fecha."""
    if not por_fecha:
        return
    existentes = {t.fecha: t for t in TasaInterna.query.filter(TasaInterna.fecha.in_(list(por_fecha)))}
    for fecha, valor in por_fecha.items():
        tasa = existentes.get(fecha)
        if tasa is None:
            tasa = TasaInterna(fecha=fecha)
            db.session.add(tasa)
        setattr(tasa, campo, valor)


def cargar_tasas(df):
    """Tasas internas por fecha (hoja TASA del libro de pedidos: columnas FECHA y TASA)."""
    tasas = {}
    for row in df.to_dict('records'):
        fecha, tasa = parsear_fecha(row.get('fecha')), numero(row.get('tasa'))
        if fecha and tasa > 0:
            tasas[fecha] = tasa
    if not tasas:
        raise ErrorCarga("No se encontraron filas con FECHA y TASA válidas.")
    registrar_tasas(tasas, 'tasa_paralelo')
    db.session.commit()
    desde, hasta = min(tasas), max(tasas)
    return (f"Tasas internas guardadas: {len(tasas)} días, del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}. "
            f"Las ventas en USD se recalculan con estas tasas.")


def cargar_inventario(df, origen, sucursal=None):
    # El reporte es una foto completa: reemplaza el inventario de ese almacén o sucursal
    # (en sucursales, también el de cargas antiguas sin sucursal).
    anterior = Inventario.query.filter(Inventario.origen_inventario == origen)
    if origen == 'INV':
        anterior = anterior.filter(or_(Inventario.sucursal == sucursal, Inventario.sucursal.is_(None)))
    anterior.delete(synchronize_session=False)

    # Precarga en memoria para evitar una consulta por fila.
    articulos = {a.codigo: a for a in Articulo.query.all()}
    existencias = {}  # si un código se repite en el archivo, prevalece la última fila
    nuevos, actualizados = 0, 0
    # Incluye los de uso interno ya guardados por cargas anteriores, para limpiarlos.
    codigos_internos = {c for c, a in articulos.items() if (a.nombredegrupo or '').upper() in GRUPOS_EXCLUIDOS}

    for row in df.to_dict('records'):
        codigo_art = codigo_articulo(row.get('codigo', row.get('cdg', row.get('codigoart'))))
        if not codigo_art or codigo_art == 'nan':
            continue

        if es_articulo_excluido(row):
            codigos_internos.add(codigo_art)
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

        existencias[codigo_art] = existencia_actual

    db.session.add_all(
        Inventario(articulo_codigo=c, origen_inventario=origen, existencia=e, sucursal=sucursal)
        for c, e in existencias.items()
    )

    if codigos_internos:
        Inventario.query.filter(Inventario.articulo_codigo.in_(codigos_internos)).delete(synchronize_session=False)
        Articulo.query.filter(Articulo.codigo.in_(codigos_internos)).delete(synchronize_session=False)

    db.session.commit()
    destino = f"de {sucursal} (INV)" if origen == 'INV' else "del Almacén Principal (INVAL)"
    mensaje = (f"Inventario {destino} guardado: {nuevos + actualizados} artículos "
               f"({nuevos} nuevos, {actualizados} actualizados).")
    if codigos_internos:
        mensaje += f" {len(codigos_internos)} ignorados por ser de uso interno (Marketing / Equipos de oficina)."
    return mensaje


def clave_sucursal(nombre):
    sin_acentos = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    return ' '.join(sin_acentos.lower().split())


def canonizar_sucursal(nombre):
    """Reutiliza el nombre ya registrado si coincide sin distinguir mayúsculas ni acentos ("MATURIN" -> "Maturín")."""
    nombre = ' '.join(texto(nombre).split())
    if not nombre:
        return ''
    existentes = {s for (s,) in db.session.query(Venta.sucursal).distinct() if s}
    existentes |= {s for (s,) in db.session.query(Inventario.sucursal).distinct() if s}
    clave = clave_sucursal(nombre)
    return next((s for s in sorted(existentes) if clave_sucursal(s) == clave), nombre.title())


# ==================== API ====================
@app.route('/api/carga_inicial', methods=['POST'])
def carga_inicial():
    tipo_reporte = request.form.get('tipo_reporte')
    archivo = request.files.get('archivo')

    if tipo_reporte not in TIPOS_REPORTE:
        return jsonify(success=False, error=f"tipo_reporte inválido. Opciones: {', '.join(sorted(TIPOS_REPORTE))}."), 400
    if not archivo or not archivo.filename:
        return jsonify(success=False, error="No se recibió ningún archivo."), 400
    # Los reportes de ventas y de inventario de sucursal no traen la sucursal: se indica al cargar.
    requiere_sucursal = tipo_reporte in ('ventas', 'inv_fisico')
    sucursal = canonizar_sucursal(request.form.get('sucursal')) if requiere_sucursal else None
    if requiere_sucursal and not sucursal:
        return jsonify(success=False, error="Indica la sucursal a la que pertenece el reporte."), 400

    try:
        df = leer_archivo(archivo, tipo_reporte)
        if tipo_reporte == 'ventas':
            mensaje = cargar_ventas(df, sucursal)
        elif tipo_reporte == 'inv_fisico':
            mensaje = cargar_inventario(df, 'INV', sucursal)
        elif tipo_reporte == 'tasas':
            mensaje = cargar_tasas(df)
        else:
            mensaje = cargar_inventario(df, 'INVAL')
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
        filtro_excepciones(excepciones_a_excluir()),
    )

    total_factura, total_costo = ventas_con_tasa(
        func.coalesce(func.sum(VENTA_USD), 0),
        func.coalesce(func.sum(Venta.costo_real_usd), 0),
    ).filter(*filtro).one()

    ventas_por_grupo = ventas_con_tasa(
        Venta.grupo_venta, func.sum(VENTA_USD)
    ).filter(*filtro).group_by(Venta.grupo_venta).order_by(func.sum(VENTA_USD).desc()).all()

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


# La demanda (ABC, traslados, última venta) solo considera ventas comerciales: reposiciones entre tiendas,
# mermas, consumo interno y servicios no son rotación de mercancía.
ES_VENTA_COMERCIAL = Venta.excepcion.is_(None)

# Facturación en USD como la hoja VENTA: Bs / tasa interna del día. Sin tasa interna para esa fecha
# (o si el archivo traía 'fact'), se usa el valor guardado al cargar.
VENTA_USD = case(
    (and_(Venta.factura_bs.isnot(None), TasaInterna.tasa_paralelo > 0), Venta.factura_bs / TasaInterna.tasa_paralelo),
    else_=Venta.factura_real_usd,
)


def ventas_con_tasa(*columnas):
    return db.session.query(*columnas).select_from(Venta).outerjoin(TasaInterna, TasaInterna.fecha == Venta.fecha_emision)


def clasificacion_abc():
    """Clasifica por rotación (unidades netas vendidas): A = primer 80% acumulado, B = siguiente 15%, C = resto."""
    unidades = db.session.query(
        Venta.articulo_codigo, func.sum(Venta.cantidad_neta)
    ).filter(ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo).order_by(func.sum(Venta.cantidad_neta).desc()).all()

    total = sum(max(int(u or 0), 0) for _, u in unidades)
    abc, acumulado = {}, 0
    for codigo, u in unidades:
        participacion_previa = acumulado / total if total else 1
        abc[codigo] = 'A' if participacion_previa < 0.80 else 'B' if participacion_previa < 0.95 else 'C'
        acumulado += max(int(u or 0), 0)
    return abc


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

    # Stock del almacén por artículo y de cada sucursal por (artículo, sucursal).
    stock_almacen, stock_sucursal = {}, {}
    for codigo, origen, sucursal, total in db.session.query(
        Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia)
    ).group_by(Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal):
        if origen == 'INVAL':
            stock_almacen[codigo] = stock_almacen.get(codigo, 0) + int(total or 0)
        else:
            stock_sucursal[(codigo, sucursal or 'Sin asignar')] = int(total or 0)
    # Solo se sugieren traslados a sucursales con inventario cargado (sin él, su stock es desconocido).
    sucursales = sorted({s for _, s in stock_sucursal})

    def venta_diaria(unidades, desde, hasta):
        rango_dias = (hasta - desde).days + 1 if desde else 30
        return int(unidades or 0) / (rango_dias if rango_dias > 0 else 1)

    vpd_sucursal = {
        (codigo, sucursal or 'Sin asignar'): venta_diaria(unidades, desde, hasta)
        for codigo, sucursal, unidades, desde, hasta in db.session.query(
            Venta.articulo_codigo, Venta.sucursal, func.sum(Venta.cantidad_neta),
            func.min(Venta.fecha_emision), func.max(Venta.fecha_emision),
        ).filter(ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo, Venta.sucursal)
    }
    vpd_total = {
        codigo: venta_diaria(unidades, desde, hasta)
        for codigo, unidades, desde, hasta in db.session.query(
            Venta.articulo_codigo, func.sum(Venta.cantidad_neta),
            func.min(Venta.fecha_emision), func.max(Venta.fecha_emision),
        ).filter(ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo)
    }

    abc = clasificacion_abc()
    resultados = []
    for art in Articulo.query.all():
        stock_inval = stock_almacen.get(art.codigo, 0)

        if tipo_analisis == 'traslado':
            if stock_inval <= 0:
                continue
            necesidades = []
            for sucursal in sucursales:
                stock_suc = stock_sucursal.get((art.codigo, sucursal), 0)
                vpd = vpd_sucursal.get((art.codigo, sucursal), 0)
                faltante = round(vpd * dias - stock_suc)
                if faltante > 0:
                    necesidades.append((stock_suc / vpd, sucursal, stock_suc, faltante))
            # Si el almacén no alcanza para todas, se atiende primero a la sucursal con menos días de cobertura.
            disponible = stock_inval
            for _, sucursal, stock_suc, faltante in sorted(necesidades):
                cant_a_mover = min(faltante, disponible)
                if cant_a_mover <= 0:
                    break
                disponible -= cant_a_mover
                resultados.append({
                    'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                    'origen': 'INVAL', 'destino': 'INV', 'sucursal': sucursal,
                    'cantidad': cant_a_mover, 'disponible_almacen': stock_inval,
                    'stock_sucursal': stock_suc, 'clasificacion_abc': abc.get(art.codigo, 'C'),
                })
        else:
            demanda_proyectada = vpd_total.get(art.codigo, 0) * dias
            stock_total = stock_inval + sum(stock_sucursal.get((art.codigo, s), 0) for s in sucursales)
            if stock_total < demanda_proyectada:
                cant_a_pedir = max(0, round(demanda_proyectada - stock_total))
                if cant_a_pedir > 0:
                    resultados.append({
                        'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                        'proveedor': art.proveedor, 'cantidad_pedir': cant_a_pedir,
                        'deficit': round(demanda_proyectada - stock_total),
                        'clasificacion_abc': abc.get(art.codigo, 'C'),
                    })

    return jsonify(success=True, tipo_analisis=tipo_analisis, dias=dias, resultados=resultados)


GRUPOS_PRINCIPALES = 5  # el resto se agrupa en "OTROS" para que el desglose sea legible


def excepciones_a_excluir():
    """?excluir=id1,id2 (vacío = facturación bruta). Sin el parámetro, las excepciones de la hoja ANAL."""
    if 'excluir' not in request.args:
        return list(EXCEPCIONES_POR_DEFECTO)
    validas = {e['id'] for e in EXCEPCIONES}
    return [x for x in request.args['excluir'].split(',') if x in validas]


def filtro_excepciones(excluir):
    return or_(Venta.excepcion.is_(None), Venta.excepcion.notin_(excluir)) if excluir else true()


@app.route('/api/ventas/analisis', methods=['GET'])
def analisis_ventas():
    """Ventas (USD a tasa interna) de un mes por sucursal y grupo, más la tendencia de los últimos 7 días."""
    corte = db.session.query(func.max(Venta.fecha_emision)).scalar()
    if corte is None:
        return jsonify(success=False, error="No hay historial de ventas cargado."), 400
    # Por defecto, el mes de la última venta registrada (los datos son una foto fija).
    mes = request.args.get('mes', default=corte.month, type=int)
    ano = request.args.get('ano', default=corte.year, type=int)
    excluir = excepciones_a_excluir()
    sin_excluidas = filtro_excepciones(excluir)

    anio_col, mes_col = func.extract('year', Venta.fecha_emision), func.extract('month', Venta.fecha_emision)
    meses_disponibles = sorted(
        {(int(a), int(m)) for a, m in db.session.query(anio_col, mes_col).distinct()}, reverse=True
    )
    del_mes = (anio_col == ano, mes_col == mes)

    # Monto de cada excepción en el mes, para que se vea cuánto mueve marcarla o desmarcarla.
    montos_excepcion = dict(ventas_con_tasa(Venta.excepcion, func.sum(VENTA_USD)).filter(
        *del_mes, Venta.excepcion.isnot(None)).group_by(Venta.excepcion).all())
    total_bruto = ventas_con_tasa(func.coalesce(func.sum(VENTA_USD), 0)).filter(*del_mes).scalar()
    dias_sin_tasa = ventas_con_tasa(func.count(func.distinct(Venta.fecha_emision))).filter(
        *del_mes, Venta.factura_bs.isnot(None), or_(TasaInterna.tasa_paralelo.is_(None), TasaInterna.tasa_paralelo <= 0)).scalar()

    sucursal_col = func.coalesce(Venta.sucursal, 'Sin asignar').label('sucursal')
    filas = ventas_con_tasa(
        sucursal_col, Venta.grupo_venta, func.sum(VENTA_USD)
    ).filter(*del_mes, sin_excluidas).group_by(sucursal_col, Venta.grupo_venta).all()

    total_por_grupo = {}
    for _, grupo, total in filas:
        total_por_grupo[grupo] = total_por_grupo.get(grupo, 0) + float(total or 0)
    principales = sorted(total_por_grupo, key=total_por_grupo.get, reverse=True)[:GRUPOS_PRINCIPALES]

    por_sucursal = {}
    for sucursal, grupo, total in filas:
        clave = grupo if grupo in principales else 'OTROS'
        grupos = por_sucursal.setdefault(sucursal, {})
        grupos[clave] = grupos.get(clave, 0) + float(total or 0)

    sucursales = sorted(
        (
            {
                'sucursal': sucursal,
                'total': round(sum(grupos.values()), 2),
                # Orden fijo (principales y luego OTROS) para que cada grupo conserve su color y posición.
                'grupos': [{'grupo': g, 'total': round(grupos[g], 2)} for g in principales + ['OTROS'] if g in grupos],
            }
            for sucursal, grupos in por_sucursal.items()
        ),
        key=lambda s: s['total'], reverse=True,
    )

    desde = corte - timedelta(days=6)
    diarios = dict(ventas_con_tasa(
        Venta.fecha_emision, func.sum(VENTA_USD)
    ).filter(Venta.fecha_emision >= desde, sin_excluidas).group_by(Venta.fecha_emision).all())
    ultimos_7_dias = [
        {'fecha': (desde + timedelta(days=i)).isoformat(), 'total': round(float(diarios.get(desde + timedelta(days=i), 0)), 2)}
        for i in range(7)
    ]

    return jsonify(
        success=True,
        fecha_corte=corte.isoformat(),
        mes=mes,
        ano=ano,
        meses_disponibles=[{'mes': m, 'ano': a} for a, m in meses_disponibles],
        total_mes=round(sum(s['total'] for s in sucursales), 2),
        total_bruto=round(float(total_bruto or 0), 2),
        # Días del mes con ventas cuyo USD se calculó con FACTOR por no haber tasa interna cargada.
        dias_sin_tasa_interna=int(dias_sin_tasa or 0),
        excepciones=[
            {'id': e['id'], 'nombre': e['nombre'], 'categoria': e['categoria'],
             'excluida': e['id'] in excluir, 'monto': round(float(montos_excepcion.get(e['id']) or 0), 2)}
            for e in EXCEPCIONES
        ],
        grupos_principales=principales,
        sucursales=sucursales,
        ultimos_7_dias=ultimos_7_dias,
    )


@app.route('/api/capital_estancado', methods=['GET'])
def capital_estancado():
    """Artículos con existencia y costo cuya última venta supera dias_min (o que no se vendieron en el historial)."""
    dias_min = request.args.get('dias_min', default=90, type=int)
    limite = request.args.get('limite', default=100, type=int)

    inicio, corte = db.session.query(func.min(Venta.fecha_emision), func.max(Venta.fecha_emision)).one()
    if corte is None:
        return jsonify(success=False, error="No hay historial de ventas cargado."), 400
    # Los días se cuentan hasta la última fecha del historial, no hasta hoy, porque los datos son una foto fija.
    dias_historial = (corte - inicio).days

    ultima_venta = dict(db.session.query(
        Venta.articulo_codigo, func.max(Venta.fecha_emision)
    ).filter(Venta.cantidad_neta > 0, ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo).all())

    almacen, por_sucursal = {}, {}
    for codigo, origen, sucursal, total in db.session.query(
        Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia)
    ).group_by(Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal):
        cantidad = max(int(total or 0), 0)
        if origen == 'INVAL':
            almacen[codigo] = almacen.get(codigo, 0) + cantidad
        elif cantidad:
            por_sucursal.setdefault(codigo, {})[sucursal or 'Sin asignar'] = cantidad

    articulos = []
    for art in Articulo.query.filter(Articulo.costoex > 0):
        sucursales = por_sucursal.get(art.codigo, {})
        existencia_sucursal = sum(sucursales.values())
        existencia_almacen = almacen.get(art.codigo, 0)
        existencia = existencia_sucursal + existencia_almacen
        if existencia <= 0:
            continue

        ultima = ultima_venta.get(art.codigo)
        dias_sin_vender = (corte - ultima).days if ultima else dias_historial
        if dias_sin_vender < dias_min:
            continue

        costo = float(art.costoex)
        articulos.append({
            'codigo': art.codigo,
            'descripcion': art.nombre,
            'grupo': art.nombredegrupo,
            'existencia': existencia,
            'existencia_sucursal': existencia_sucursal,
            'existencia_por_sucursal': dict(sorted(sucursales.items())),
            'existencia_almacen': existencia_almacen,
            'costo_unitario': round(costo, 4),
            'dias_sin_vender': dias_sin_vender,
            'sin_ventas': ultima is None,
            'ultima_venta': ultima.isoformat() if ultima else None,
            'capital_estancado': round(existencia * costo, 2),
        })

    articulos.sort(key=lambda a: a['capital_estancado'], reverse=True)
    total = len(articulos)
    return jsonify(
        success=True,
        fecha_corte=corte.isoformat(),
        dias_historial=dias_historial,
        dias_min=dias_min,
        resumen={
            'capital_total': round(sum(a['capital_estancado'] for a in articulos), 2),
            'articulos': total,
            'sin_ventas': sum(a['sin_ventas'] for a in articulos),
            'promedio_dias': round(sum(a['dias_sin_vender'] for a in articulos) / total) if total else 0,
        },
        articulos=articulos[:limite],
    )


@app.route('/api/tasas', methods=['GET'])
def listar_tasas():
    """Tasas BCV e interna vigentes en ?fecha= (por defecto hoy) y el historial de los ?dias= anteriores."""
    fecha = parsear_fecha(request.args.get('fecha')) or datetime.today().date()
    dias = request.args.get('dias', default=30, type=int)

    def vigente(columna):
        # Última tasa registrada en o antes de la fecha (fines de semana y feriados no tienen tasa BCV propia).
        t = TasaInterna.query.filter(TasaInterna.fecha <= fecha, columna.isnot(None)).order_by(TasaInterna.fecha.desc()).first()
        return {'fecha': t.fecha.isoformat(), 'valor': float(getattr(t, columna.key))} if t else None

    historial = TasaInterna.query.filter(
        TasaInterna.fecha <= fecha, TasaInterna.fecha > fecha - timedelta(days=dias)
    ).order_by(TasaInterna.fecha.desc()).all()
    desde, hasta = db.session.query(func.min(TasaInterna.fecha), func.max(TasaInterna.fecha)).one()

    return jsonify(
        success=True,
        fecha=fecha.isoformat(),
        bcv=vigente(TasaInterna.tasa_bcv),
        interna=vigente(TasaInterna.tasa_paralelo),
        rango={'desde': desde.isoformat() if desde else None, 'hasta': hasta.isoformat() if hasta else None},
        historial=[
            {'fecha': t.fecha.isoformat(),
             'bcv': float(t.tasa_bcv) if t.tasa_bcv is not None else None,
             'interna': float(t.tasa_paralelo) if t.tasa_paralelo is not None else None}
            for t in historial
        ],
    )


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


COLUMNAS_AGREGADAS = [
    ('ventas', 'sucursal', 'VARCHAR(100)'),
    ('inventarios', 'sucursal', 'VARCHAR(100)'),
    ('ventas', 'factura_bs', 'NUMERIC(16,4)'),
    ('ventas', 'excepcion', 'VARCHAR(50)'),
    ('tasas_internas', 'tasa_bcv', 'NUMERIC(12,4)'),
]


def migrar_esquema():
    """create_all no agrega columnas a tablas existentes: se añaden aquí las incorporadas después."""
    inspector = inspect(db.engine)
    for tabla, columna, tipo in COLUMNAS_AGREGADAS:
        if columna not in {c['name'] for c in inspector.get_columns(tabla)}:
            with db.engine.begin() as conexion:
                conexion.execute(text(f'ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}'))
    # tasa_paralelo era obligatoria; ahora una fecha puede tener solo tasa BCV.
    if db.engine.dialect.name == 'postgresql':
        with db.engine.begin() as conexion:
            conexion.execute(text('ALTER TABLE tasas_internas ALTER COLUMN tasa_paralelo DROP NOT NULL'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrar_esquema()
    app.run(host='127.0.0.1', port=5000, debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
