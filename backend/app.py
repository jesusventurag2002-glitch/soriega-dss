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
    precio_usd = db.Column(db.Numeric(12, 4))  # precio de venta en USD sin IVA en esa ubicación

class TasaInterna(db.Model):
    __tablename__ = 'tasas_internas'
    fecha = db.Column(db.Date, primary_key=True)
    tasa_paralelo = db.Column(db.Numeric(12, 4))  # tasa interna del día (hoja TASA / sistema)
    tasa_bcv = db.Column(db.Numeric(12, 4))  # tasa BCV del día (FACTOR del reporte de ventas)

class ConfigExcepcion(db.Model):
    """Excepciones elegidas en "Administrar excepciones"; sin fila, rige el valor por defecto de EXCEPCIONES."""
    __tablename__ = 'config_excepciones'
    id = db.Column(db.String(50), primary_key=True)
    excluida = db.Column(db.Boolean, nullable=False)

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

class DocumentoTraslado(db.Model):
    """Documento de traslado (TR-…): agrupa los artículos de una misma ruta y lleva el ciclo de vida completo."""
    __tablename__ = 'traslado_documentos'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default='reposicion')  # 'reposicion' (almacén -> sucursal) o 'retorno'
    origen = db.Column(db.String(100), nullable=False, index=True)
    destino = db.Column(db.String(100), nullable=False, index=True)
    estado = db.Column(db.String(30), nullable=False, default='borrador', index=True)
    horizonte_dias = db.Column(db.Integer)
    motivo_rechazo = db.Column(db.Text)
    observaciones = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    actualizado_en = db.Column(db.DateTime, nullable=False)
    # Se incrementa en cada cambio: una acción enviada con una versión vieja (doble clic, otra pestaña) se rechaza.
    version = db.Column(db.Integer, nullable=False, default=1)
    lineas = db.relationship('Traslado', backref='documento', order_by='Traslado.id', lazy='selectin')

class EventoDocumento(db.Model):
    """Historial inmutable de cada documento: quién hizo qué, cuándo y con qué valores antes y después."""
    __tablename__ = 'traslado_documento_eventos'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('traslado_documentos.id'), nullable=False, index=True)
    tipo = db.Column(db.String(40), nullable=False)
    estado_anterior = db.Column(db.String(30))
    estado_nuevo = db.Column(db.String(30))
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(30))
    fecha = db.Column(db.DateTime, nullable=False, index=True)
    detalle = db.Column(db.Text)  # JSON: {"antes": {...}, "despues": {...}, "comentario": "...", "articulos": [...]}

class Traslado(db.Model):
    """Línea de un documento de traslado: un artículo con sus cantidades en cada etapa del ciclo.

    Su estado replica el del documento (las consultas de stock comprometido y de traslados abiertos lo usan);
    una línea retirada de un borrador queda 'descartado' con retirado_en.
    """
    __tablename__ = 'traslados'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('traslado_documentos.id'), index=True)
    retirado_en = db.Column(db.DateTime)
    articulo_codigo = db.Column(db.String(50), nullable=False, index=True)
    articulo_nombre = db.Column(db.String(255), nullable=False)
    clasificacion_abc = db.Column(db.String(1))
    tipo = db.Column(db.String(20), nullable=False, default='reposicion')  # 'reposicion' (almacén -> sucursal) o 'retorno'
    origen = db.Column(db.String(100), nullable=False)  # ALMACEN o nombre de sucursal
    destino = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(30), nullable=False, default='borrador', index=True)
    cantidad_sugerida = db.Column(db.Integer, nullable=False)
    cantidad_aprobada = db.Column(db.Integer)
    cantidad_despachada = db.Column(db.Integer)
    cantidad_recibida = db.Column(db.Integer)
    # Foto del momento en que se generó la propuesta (las existencias vienen de exportaciones).
    stock_origen = db.Column(db.Integer)
    stock_destino = db.Column(db.Integer)
    cobertura_dias = db.Column(db.Float)  # días que cubría el stock del destino; menor = más urgente
    horizonte_dias = db.Column(db.Integer)
    motivo_rechazo = db.Column(db.Text)
    observaciones = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    actualizado_en = db.Column(db.DateTime, nullable=False)
    # Se incrementa en cada cambio: una acción enviada con una versión vieja (doble clic, otra pestaña) se rechaza.
    version = db.Column(db.Integer, nullable=False, default=1)

class EventoTraslado(db.Model):
    """Historial por artículo anterior a los documentos de traslado; se conserva y se copia al documento al migrar."""
    __tablename__ = 'traslado_eventos'
    id = db.Column(db.Integer, primary_key=True)
    traslado_id = db.Column(db.Integer, db.ForeignKey('traslados.id'), nullable=False, index=True)
    tipo = db.Column(db.String(40), nullable=False)
    estado_anterior = db.Column(db.String(30))
    estado_nuevo = db.Column(db.String(30))
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(30))
    fecha = db.Column(db.DateTime, nullable=False, index=True)
    detalle = db.Column(db.Text)  # JSON: {"antes": {...}, "despues": {...}, "comentario": "..."}

class Discrepancia(db.Model):
    """Alerta del piso de venta: lo contado físicamente en la tienda no coincide con el inventario del sistema."""
    __tablename__ = 'discrepancias'
    id = db.Column(db.Integer, primary_key=True)
    articulo_codigo = db.Column(db.String(50), nullable=False, index=True)
    articulo_nombre = db.Column(db.String(255), nullable=False)
    sucursal = db.Column(db.String(100), nullable=False, index=True)
    existencia_sistema = db.Column(db.Integer, nullable=False)  # foto del inventario cargado al reportar
    existencia_contada = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    estado = db.Column(db.String(20), nullable=False, default='pendiente', index=True)  # pendiente | revisada
    resolucion = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    revisado_por = db.Column(db.String(100))
    revisado_en = db.Column(db.DateTime)

class AccionEstancado(db.Model):
    """Seguimiento de decisiones sobre mercancía estancada (promoción o devolución a proveedor)."""
    __tablename__ = 'acciones_estancado'
    id = db.Column(db.Integer, primary_key=True)
    articulo_codigo = db.Column(db.String(50), nullable=False, index=True)
    articulo_nombre = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # 'promocion' | 'devolucion_proveedor'
    estado = db.Column(db.String(20), nullable=False, default='pendiente')  # pendiente | completada | descartada
    capital_al_registrar = db.Column(db.Numeric(14, 2))
    comentario = db.Column(db.Text)
    resultado = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    cerrado_por = db.Column(db.String(100))
    cerrado_en = db.Column(db.DateTime)

class Importacion(db.Model):
    """Registro de cada archivo cargado, para saber de cuándo son los datos que se muestran."""
    __tablename__ = 'importaciones'
    id = db.Column(db.Integer, primary_key=True)
    tipo_reporte = db.Column(db.String(20), nullable=False)
    sucursal = db.Column(db.String(100))
    archivo = db.Column(db.String(255))
    exito = db.Column(db.Boolean, nullable=False)
    mensaje = db.Column(db.Text)
    fecha_importacion = db.Column(db.DateTime, nullable=False)
    datos_hasta = db.Column(db.Date)  # última fecha contenida en el archivo, cuando la trae (ventas, tasas)
    usuario = db.Column(db.String(100))


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


def precio_venta_usd(row, origen):
    """Precio de venta en USD sin IVA. Las sucursales lo traen en PRECIO1EX (PRECIO1 está en Bs); el almacén
    principal trabaja en USD y lo trae en PRECIO1, con PRECIO1EX vacío."""
    precio = numero(row.get('precio1ex'))
    if precio <= 0 and origen == 'INVAL':
        precio = numero(row.get('precio1'))
    return round(precio, 4) if precio > 0 else None


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
            f"Las ventas en USD se recalculan con estas tasas."), hasta


def cargar_inventario(df, origen, sucursal=None):
    # El reporte es una foto completa: reemplaza el inventario de ese almacén o sucursal
    # (en sucursales, también el de cargas antiguas sin sucursal).
    anterior = Inventario.query.filter(Inventario.origen_inventario == origen)
    if origen == 'INV':
        anterior = anterior.filter(or_(Inventario.sucursal == sucursal, Inventario.sucursal.is_(None)))
    anterior.delete(synchronize_session=False)

    # Precarga en memoria para evitar una consulta por fila.
    articulos = {a.codigo: a for a in Articulo.query.all()}
    existencias, precios = {}, {}  # si un código se repite en el archivo, prevalece la última fila
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
        precios[codigo_art] = precio_venta_usd(row, origen)

    db.session.add_all(
        Inventario(articulo_codigo=c, origen_inventario=origen, existencia=e, sucursal=sucursal, precio_usd=precios[c])
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

    def registrar_importacion(exito, mensaje, datos_hasta=None):
        db.session.add(Importacion(
            tipo_reporte=tipo_reporte, sucursal=sucursal, archivo=archivo.filename[:255], exito=exito,
            mensaje=mensaje, fecha_importacion=datetime.now(), datos_hasta=datos_hasta, usuario=usuario_actual()[0],
        ))
        db.session.commit()

    try:
        df = leer_archivo(archivo, tipo_reporte)
        datos_hasta = None
        if tipo_reporte == 'ventas':
            mensaje = cargar_ventas(df, sucursal)
            datos_hasta = db.session.query(func.max(Venta.fecha_emision)).filter(Venta.sucursal == sucursal).scalar()
        elif tipo_reporte == 'inv_fisico':
            mensaje = cargar_inventario(df, 'INV', sucursal)
        elif tipo_reporte == 'tasas':
            mensaje, datos_hasta = cargar_tasas(df)
        else:
            mensaje = cargar_inventario(df, 'INVAL')
        registrar_importacion(True, mensaje, datos_hasta)
        return jsonify(success=True, message=mensaje), 200
    except ErrorCarga as e:
        db.session.rollback()
        registrar_importacion(False, str(e))
        return jsonify(success=False, error=str(e)), 400
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Error procesando carga inicial")
        registrar_importacion(False, str(e))
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


def datos_demanda():
    """Stock (almacén y por sucursal) y venta diaria comercial por artículo, insumos de traslados y alertas."""
    stock_almacen, stock_sucursal = {}, {}
    for codigo, origen, sucursal, total in db.session.query(
        Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia)
    ).group_by(Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal):
        if origen == 'INVAL':
            stock_almacen[codigo] = stock_almacen.get(codigo, 0) + int(total or 0)
        else:
            stock_sucursal[(codigo, sucursal or 'Sin asignar')] = int(total or 0)
    # Solo se consideran sucursales con inventario cargado (sin él, su stock es desconocido).
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
    return stock_almacen, stock_sucursal, sucursales, vpd_sucursal, vpd_total


def calcular_sugerencias_traslado(dias, comprometido_almacen=None):
    """Necesidad de cada sucursal (venta diaria * días - stock) cubierta con el stock del almacén.

    comprometido_almacen: unidades del almacén ya reservadas en traslados abiertos, que no se vuelven a repartir.
    """
    stock_almacen, stock_sucursal, sucursales, vpd_sucursal, _ = datos_demanda()
    comprometido_almacen = comprometido_almacen or {}
    abc = clasificacion_abc()
    resultados = []
    for art in Articulo.query.all():
        stock_inval = stock_almacen.get(art.codigo, 0)
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
        disponible = stock_inval - comprometido_almacen.get(art.codigo, 0)
        for cobertura, sucursal, stock_suc, faltante in sorted(necesidades):
            cant_a_mover = min(faltante, disponible)
            if cant_a_mover <= 0:
                break
            disponible -= cant_a_mover
            resultados.append({
                'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                'origen': 'INVAL', 'destino': 'INV', 'sucursal': sucursal,
                'cantidad': cant_a_mover, 'disponible_almacen': stock_inval,
                'stock_sucursal': stock_suc, 'clasificacion_abc': abc.get(art.codigo, 'C'),
                'cobertura_dias': round(cobertura, 1),
            })
    return resultados


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

    if tipo_analisis == 'traslado':
        return jsonify(success=True, tipo_analisis=tipo_analisis, dias=dias, resultados=calcular_sugerencias_traslado(dias))

    stock_almacen, stock_sucursal, sucursales, _, vpd_total = datos_demanda()
    abc = clasificacion_abc()
    resultados = []
    for art in Articulo.query.all():
        stock_inval = stock_almacen.get(art.codigo, 0)
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


def excepciones_configuradas():
    """Ids excluidos según "Administrar excepciones" (por defecto, los de la hoja ANAL)."""
    guardadas = {c.id: c.excluida for c in ConfigExcepcion.query}
    return [e['id'] for e in EXCEPCIONES if guardadas.get(e['id'], e.get('por_defecto', True))]


def excepciones_a_excluir():
    """?excluir=id1,id2 (vacío = facturación bruta) para una consulta puntual; sin el parámetro, la configuración guardada."""
    if 'excluir' not in request.args:
        return excepciones_configuradas()
    validas = {e['id'] for e in EXCEPCIONES}
    return [x for x in request.args['excluir'].split(',') if x in validas]


def filtro_excepciones(excluir):
    return or_(Venta.excepcion.is_(None), Venta.excepcion.notin_(excluir)) if excluir else true()


@app.route('/api/excepciones', methods=['PUT'])
def guardar_excepciones():
    """{"excluir": [ids]} guarda qué excepciones se excluyen; {"restablecer": true} vuelve a las de la hoja ANAL."""
    datos = request.get_json(silent=True) or {}
    validas = {e['id'] for e in EXCEPCIONES}
    if datos.get('restablecer'):
        ConfigExcepcion.query.delete()
    else:
        excluir = datos.get('excluir')
        if not isinstance(excluir, list) or not set(excluir) <= validas:
            return jsonify(success=False, error="'excluir' debe ser una lista de ids de excepción válidos."), 400
        for id_ in validas:
            config = db.session.get(ConfigExcepcion, id_) or ConfigExcepcion(id=id_)
            config.excluida = id_ in excluir
            db.session.add(config)
    db.session.commit()
    return jsonify(success=True, excluidas=excepciones_configuradas())


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
    sin_costo = or_(Venta.costo_real_usd.is_(None), Venta.costo_real_usd == 0)
    filas = ventas_con_tasa(
        sucursal_col, Venta.grupo_venta, func.sum(VENTA_USD), func.sum(func.coalesce(Venta.costo_real_usd, 0)),
        func.sum(case((sin_costo, VENTA_USD), else_=0)),
    ).filter(*del_mes, sin_excluidas).group_by(sucursal_col, Venta.grupo_venta).all()

    total_por_grupo = {}
    for _, grupo, total, _, _ in filas:
        total_por_grupo[grupo] = total_por_grupo.get(grupo, 0) + float(total or 0)
    principales = sorted(total_por_grupo, key=total_por_grupo.get, reverse=True)[:GRUPOS_PRINCIPALES]

    # Por sucursal: los grupos principales con el resto en OTROS (para el gráfico) y todos los grupos (para la tabla).
    por_sucursal, todos = {}, {}
    for sucursal, grupo, total, costo, venta_sin_costo in filas:
        valores = (float(total or 0), float(costo or 0), float(venta_sin_costo or 0))
        for destino, clave in ((por_sucursal, grupo if grupo in principales else 'OTROS'), (todos, grupo)):
            actual = destino.setdefault(sucursal, {}).get(clave, (0, 0, 0))
            destino[sucursal][clave] = tuple(a + b for a, b in zip(actual, valores))

    def rentabilidad(nombre, total, costo, venta_sin_costo):
        """Utilidad = ventas - costo (ambos con IVA, como en la hoja ANAL); margen sobre ventas."""
        utilidad = total - costo
        return {'grupo': nombre, 'total': round(total, 2), 'costo': round(costo, 2), 'utilidad': round(utilidad, 2),
                'margen': round(utilidad / total * 100, 1) if total else None, 'ventas_sin_costo': round(venta_sin_costo, 2)}

    def resumen(sucursal):
        grupos, completos = por_sucursal[sucursal], todos[sucursal]
        total, costo, venta_sin_costo = (sum(v[i] for v in grupos.values()) for i in range(3))
        datos = rentabilidad(None, total, costo, venta_sin_costo)
        del datos['grupo']
        return {
            'sucursal': sucursal, **datos,
            # Orden fijo (principales y luego OTROS) para que cada grupo conserve su color y posición.
            'grupos': [rentabilidad(g, *grupos[g]) for g in principales + ['OTROS'] if g in grupos],
            'todos_los_grupos': sorted((rentabilidad(g, *v) for g, v in completos.items()), key=lambda g: g['total'], reverse=True),
        }

    sucursales = sorted((resumen(s) for s in por_sucursal), key=lambda s: s['total'], reverse=True)

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
        costo_mes=round(sum(s['costo'] for s in sucursales), 2),
        utilidad_mes=round(sum(s['utilidad'] for s in sucursales), 2),
        ventas_sin_costo_mes=round(sum(s['ventas_sin_costo'] for s in sucursales), 2),
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


def calcular_capital_estancado(dias_min, sucursal=None):
    """Artículos con existencia y costo cuya última venta supera dias_min (o que no se vendieron en el historial).

    Sin sucursal: existencia consolidada (todas las sucursales + almacén). Con sucursal (o ALMACEN): solo la de esa
    ubicación. Devuelve None si no hay ventas cargadas.
    """
    inicio, corte = db.session.query(func.min(Venta.fecha_emision), func.max(Venta.fecha_emision)).one()
    if corte is None:
        return None
    # Los días se cuentan hasta la última fecha del historial, no hasta hoy, porque los datos son una foto fija.
    dias_historial = (corte - inicio).days

    ultima_venta = dict(db.session.query(
        Venta.articulo_codigo, func.max(Venta.fecha_emision)
    ).filter(Venta.cantidad_neta > 0, ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo).all())

    almacen, por_sucursal = {}, {}
    for codigo, origen, ubicacion, total in db.session.query(
        Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia)
    ).group_by(Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal):
        cantidad = max(int(total or 0), 0)
        if origen == 'INVAL':
            almacen[codigo] = almacen.get(codigo, 0) + cantidad
        elif cantidad:
            por_sucursal.setdefault(codigo, {})[ubicacion or 'Sin asignar'] = cantidad

    articulos = []
    for art in Articulo.query.filter(Articulo.costoex > 0):
        sucursales = por_sucursal.get(art.codigo, {})
        if sucursal and sucursal != ALMACEN:
            sucursales = {sucursal: sucursales[sucursal]} if sucursal in sucursales else {}
        existencia_sucursal = sum(sucursales.values())
        existencia_almacen = almacen.get(art.codigo, 0) if sucursal in (None, ALMACEN) else 0
        if sucursal == ALMACEN:
            sucursales, existencia_sucursal = {}, 0
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
    return {
        'fecha_corte': corte.isoformat(),
        'dias_historial': dias_historial,
        'dias_min': dias_min,
        'sucursal': sucursal,
        'resumen': {
            'capital_total': round(sum(a['capital_estancado'] for a in articulos), 2),
            'articulos': total,
            'sin_ventas': sum(a['sin_ventas'] for a in articulos),
            'promedio_dias': round(sum(a['dias_sin_vender'] for a in articulos) / total) if total else 0,
        },
        'articulos': articulos,
    }


@app.route('/api/capital_estancado', methods=['GET'])
def capital_estancado():
    dias_min = request.args.get('dias_min', default=90, type=int)
    limite = request.args.get('limite', default=100, type=int)
    datos = calcular_capital_estancado(dias_min, texto(request.args.get('sucursal')) or None)
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


# ==================== TRASLADOS ====================
# Un documento de traslado (TR-…) agrupa los artículos que van por una misma ruta (origen -> destino) y se
# aprueba, despacha y recibe como una sola operación. Cada artículo es una línea (modelo Traslado).
ALMACEN = 'Almacén Principal'

ESTADOS_TRASLADO = {
    'borrador': 'Borrador',
    'pendiente_aprobacion': 'Pendiente de aprobación',
    'aprobado': 'Aprobado',
    'rechazado': 'Rechazado',
    'descartado': 'Descartado',
    'despachado': 'Despachado',
    'recibido': 'Recibido',
    'recibido_con_diferencias': 'Recibido con diferencias',
    'cerrado': 'Cerrado',
}
ESTADOS_ABIERTOS = ['borrador', 'pendiente_aprobacion', 'aprobado', 'despachado', 'recibido', 'recibido_con_diferencias']
# Unidades reservadas en el origen: todavía no salieron y no deben asignarse a otro traslado. Lo despachado no se
# descuenta porque las existencias vienen de exportaciones y la siguiente ya reflejará la salida.
ESTADOS_COMPROMETEN_ORIGEN = ['pendiente_aprobacion', 'aprobado']

# acción -> (estados desde los que se permite, roles autorizados; None = cualquier rol)
TRANSICIONES = {
    'enviar': (['borrador'], None),
    'descartar': (['borrador'], None),
    'aprobar': (['pendiente_aprobacion'], ['gerente']),
    'rechazar': (['pendiente_aprobacion'], ['gerente']),
    'despachar': (['aprobado'], None),
    'recibir': (['despachado'], None),
    'cerrar': (['recibido', 'recibido_con_diferencias'], ['gerente']),
}
VERBOS = {'enviar': 'enviar a aprobación', 'descartar': 'descartar', 'aprobar': 'aprobar', 'rechazar': 'rechazar',
          'despachar': 'despachar', 'recibir': 'recibir', 'cerrar': 'cerrar'}
# Agrupaciones de estados para las pestañas de la bandeja.
GRUPOS_ESTADO = {
    'activos': ESTADOS_ABIERTOS,
    'borradores': ['borrador'],
    'por_aprobar': ['pendiente_aprobacion'],
    'por_despachar': ['aprobado'],
    'en_transito': ['despachado'],
    'por_cerrar': ['recibido', 'recibido_con_diferencias'],
    'cerrados': ['cerrado'],
    'rechazados': ['rechazado', 'descartado'],
    'todos': list(ESTADOS_TRASLADO),
}


class ErrorTraslado(Exception):
    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.status = status


def usuario_actual():
    """Responsable de la acción según el login simulado del frontend (cabeceras X-Usuario / X-Rol, codificadas).

    No es autenticación: identifica a quien opera mientras no exista un inicio de sesión real.
    """
    nombre = unquote(request.headers.get('X-Usuario', '')).strip()[:100] or 'Sin identificar'
    rol = unquote(request.headers.get('X-Rol', '')).strip().lower()[:30]
    return nombre, rol


def folio(d):
    return f'TR-{d.id:05d}'


def cantidad_vigente(t):
    """La cantidad más reciente del ciclo: recibida, despachada, aprobada o sugerida."""
    return next(v for v in (t.cantidad_recibida, t.cantidad_despachada, t.cantidad_aprobada, t.cantidad_sugerida) if v is not None)


def diferencia_de(t):
    return (t.cantidad_recibida - t.cantidad_despachada
            if t.cantidad_recibida is not None and t.cantidad_despachada is not None else None)


def lineas_vigentes(d):
    return [l for l in d.lineas if l.retirado_en is None]


ORDEN_CLASE = {'A': 0, 'B': 1, 'C': 2}


def prioridad_linea(t):
    """Clase ABC y luego la cobertura del destino (menos días = más urgente)."""
    return ORDEN_CLASE.get(t.clasificacion_abc, 3), t.cobertura_dias is None, t.cobertura_dias or 0, t.id


def acciones_disponibles(d, rol):
    return [a for a, (desde, roles) in TRANSICIONES.items() if d.estado in desde and (roles is None or rol in roles)]


def puede_retirar(d, rol):
    """En borrador cualquiera ajusta el documento; en aprobación solo el gerente puede quitar un artículo."""
    return d.estado == 'borrador' or (d.estado == 'pendiente_aprobacion' and rol == 'gerente')


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
        'cantidad_recibida': t.cantidad_recibida, 'diferencia': diferencia_de(t),
        'stock_origen': t.stock_origen, 'stock_destino': t.stock_destino, 'cobertura_dias': t.cobertura_dias,
    }


def resumen_documento(d):
    """Datos de un documento para listas: ruta, estado y totales de sus artículos."""
    lineas = sorted(lineas_vigentes(d), key=prioridad_linea)
    abc = {c: sum(1 for l in lineas if l.clasificacion_abc == c) for c in 'ABC'}
    return {
        'id': d.id, 'folio': folio(d), 'tipo': d.tipo, 'origen': d.origen, 'destino': d.destino, 'estado': d.estado,
        'estado_etiqueta': ESTADOS_TRASLADO[d.estado], 'total_articulos': len(lineas),
        'total_unidades': sum(cantidad_vigente(l) for l in lineas), 'abc': abc,
        'clasificacion_abc': next((c for c in 'ABC' if abc[c]), None),
        'con_diferencias': sum(1 for l in lineas if diferencia_de(l)),
        'articulos': [l.articulo_nombre for l in lineas[:3]],
        'actualizado_en': d.actualizado_en.isoformat(timespec='seconds'),
    }


def serializar_documento(d, rol=None, detalle=False):
    datos = {
        **resumen_documento(d),
        'horizonte_dias': d.horizonte_dias, 'motivo_rechazo': d.motivo_rechazo, 'observaciones': d.observaciones,
        'creado_por': d.creado_por, 'creado_en': d.creado_en.isoformat(timespec='seconds'), 'version': d.version,
        'acciones': acciones_disponibles(d, rol), 'editable': d.estado == 'borrador', 'retirable': puede_retirar(d, rol),
    }
    if detalle:
        datos['lineas'] = [serializar_linea(l) for l in sorted(lineas_vigentes(d), key=prioridad_linea)]
        eventos = EventoDocumento.query.filter_by(documento_id=d.id).order_by(EventoDocumento.fecha, EventoDocumento.id)
        datos['eventos'] = [serializar_evento(e) for e in eventos]
    return datos


def ref_articulo(t, antes=None, despues=None):
    """Artículo afectado por un evento del documento, con sus valores antes y después."""
    return {k: v for k, v in (('codigo', t.articulo_codigo), ('nombre', t.articulo_nombre), ('antes', antes),
                              ('despues', despues)) if v is not None}


def registrar_evento(d, tipo, usuario, estado_anterior=None, antes=None, despues=None, comentario=None, articulos=None):
    detalle = {k: v for k, v in (('antes', antes), ('despues', despues), ('comentario', comentario),
                                 ('articulos', articulos)) if v}
    db.session.add(EventoDocumento(
        documento_id=d.id, tipo=tipo, estado_anterior=estado_anterior, estado_nuevo=d.estado,
        usuario=usuario[0], rol=usuario[1], fecha=datetime.now(),
        detalle=json.dumps(detalle, ensure_ascii=False) if detalle else None,
    ))


def fijar_estado(d, estado):
    """El documento y sus artículos vigentes cambian de estado juntos."""
    d.estado = estado
    for l in lineas_vigentes(d):
        l.estado = estado


def tocar(d):
    ahora = datetime.now()
    d.version += 1
    d.actualizado_en = ahora
    for l in lineas_vigentes(d):
        l.actualizado_en = ahora


def entero(valor, campo, minimo=0):
    if isinstance(valor, bool) or (isinstance(valor, float) and not valor.is_integer()):
        raise ErrorTraslado(f"{campo} debe ser un número entero.")
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ErrorTraslado(f"{campo} debe ser un número entero.")
    if n < minimo:
        raise ErrorTraslado(f"{campo} debe ser mayor o igual a {minimo}.")
    return n


def stock_en(ubicacion, codigo):
    q = db.session.query(func.coalesce(func.sum(Inventario.existencia), 0)).filter(Inventario.articulo_codigo == codigo)
    if ubicacion == ALMACEN:
        q = q.filter(Inventario.origen_inventario == 'INVAL')
    else:
        q = q.filter(Inventario.origen_inventario == 'INV', Inventario.sucursal == ubicacion)
    return int(q.scalar() or 0)


def comprometido_en(ubicacion, codigo, excluir_id=None):
    q = Traslado.query.filter(Traslado.articulo_codigo == codigo, Traslado.origen == ubicacion,
                              Traslado.estado.in_(ESTADOS_COMPROMETEN_ORIGEN))
    if excluir_id:
        q = q.filter(Traslado.id != excluir_id)
    return sum(t.cantidad_aprobada if t.cantidad_aprobada is not None else t.cantidad_sugerida for t in q)


def validar_disponible(t, cantidad):
    """No se puede reservar más de lo que hay en el origen descontando lo reservado por otros traslados."""
    existencia = stock_en(t.origen, t.articulo_codigo)
    reservado = comprometido_en(t.origen, t.articulo_codigo, t.id)
    disponible = existencia - reservado
    if cantidad > disponible:
        raise ErrorTraslado(
            f"{t.articulo_nombre}: {t.origen} tiene {max(disponible, 0)} unidades disponibles "
            f"(existencia {existencia}, {reservado} reservadas en otros traslados). Ajusta la cantidad.")


def verificar_version(d, datos):
    version = datos.get('version')
    if version is None:
        raise ErrorTraslado("Falta la versión del traslado.")
    if entero(version, 'La versión') != d.version:
        raise ErrorTraslado(
            f"{folio(d)} cambió mientras lo revisabas (ahora está «{ESTADOS_TRASLADO[d.estado]}»). "
            "Se cargó la información actualizada; revisa antes de continuar.", 409)


def cantidades_indicadas(d, datos, etiqueta, defecto=None, minimo=0):
    """Cantidad por artículo de {"cantidades": {"<id de línea>": n}}; si falta, se usa `defecto(línea)`."""
    indicadas = datos.get('cantidades') or {}
    if not isinstance(indicadas, dict):
        raise ErrorTraslado("Las cantidades deben indicarse por artículo.")
    lineas = {str(l.id): l for l in lineas_vigentes(d)}
    ajenas = set(map(str, indicadas)) - set(lineas)
    if ajenas:
        raise ErrorTraslado(f"{folio(d)} no contiene los artículos indicados ({', '.join(sorted(ajenas))}).")
    resultado = {}
    for clave, l in lineas.items():
        valor = indicadas.get(clave, indicadas.get(l.id))
        if valor in (None, ''):
            valor = defecto(l) if defecto else None
            if valor is None:
                raise ErrorTraslado(f"Indica la {etiqueta.lower()} de {l.articulo_nombre}.")
        resultado[l] = entero(valor, f"{etiqueta} de {l.articulo_nombre}", minimo)
    return resultado


def cambios_de(cantidades, campo_antes, campo_despues):
    """Artículos cuya cantidad cambió respecto a la etapa anterior, para el historial."""
    return [ref_articulo(l, {campo_antes: getattr(l, campo_antes)}, {campo_despues: n})
            for l, n in cantidades.items() if n != getattr(l, campo_antes)]


def aplicar_accion(d, accion, datos, usuario):
    """Ejecuta una transición sobre el documento completo validando estado, rol y cantidades de cada artículo."""
    if accion not in TRANSICIONES:
        raise ErrorTraslado(f"Acción desconocida: {accion}.")
    desde, roles = TRANSICIONES[accion]
    if d.estado not in desde:
        raise ErrorTraslado(f"No se puede {VERBOS[accion]} {folio(d)} porque está «{ESTADOS_TRASLADO[d.estado]}».", 409)
    if roles and usuario[1] not in roles:
        raise ErrorTraslado(f"Solo un gerente puede {VERBOS[accion]} un traslado.", 403)
    lineas = lineas_vigentes(d)
    if not lineas:
        raise ErrorTraslado(f"{folio(d)} no tiene artículos.")

    anterior = d.estado
    comentario = texto(datos.get('comentario'))
    if accion == 'enviar':
        for l in lineas:
            validar_disponible(l, l.cantidad_sugerida)
        fijar_estado(d, 'pendiente_aprobacion')
        registrar_evento(d, 'enviado_aprobacion', usuario, anterior, comentario=comentario)
    elif accion == 'descartar':
        d.motivo_rechazo = comentario or None
        fijar_estado(d, 'descartado')
        registrar_evento(d, 'descartado', usuario, anterior, comentario=comentario)
    elif accion == 'aprobar':
        cantidades = cantidades_indicadas(d, datos, 'La cantidad aprobada', lambda l: l.cantidad_sugerida, 1)
        for l, n in cantidades.items():
            validar_disponible(l, n)
        cambios = cambios_de(cantidades, 'cantidad_sugerida', 'cantidad_aprobada')
        for l, n in cantidades.items():
            l.cantidad_aprobada = n
        fijar_estado(d, 'aprobado')
        registrar_evento(d, 'aprobado', usuario, anterior, despues={'unidades_aprobadas': sum(cantidades.values())},
                         comentario=comentario, articulos=cambios)
    elif accion == 'rechazar':
        motivo = texto(datos.get('motivo'))
        if len(motivo) < 3:
            raise ErrorTraslado("Indica el motivo del rechazo.")
        d.motivo_rechazo = motivo
        fijar_estado(d, 'rechazado')
        registrar_evento(d, 'rechazado', usuario, anterior, comentario=motivo)
    elif accion == 'despachar':
        cantidades = cantidades_indicadas(d, datos, 'La cantidad despachada', lambda l: l.cantidad_aprobada, 0)
        for l, n in cantidades.items():
            if n > l.cantidad_aprobada:
                raise ErrorTraslado(f"{l.articulo_nombre}: no se puede despachar más de lo aprobado ({l.cantidad_aprobada}).")
        if not sum(cantidades.values()):
            raise ErrorTraslado("Indica al menos un artículo despachado.")
        cambios = cambios_de(cantidades, 'cantidad_aprobada', 'cantidad_despachada')
        for l, n in cantidades.items():
            l.cantidad_despachada = n
        fijar_estado(d, 'despachado')
        registrar_evento(d, 'despachado', usuario, anterior, despues={'unidades_despachadas': sum(cantidades.values())},
                         comentario=comentario, articulos=cambios)
    elif accion == 'recibir':
        cantidades = cantidades_indicadas(d, datos, 'La cantidad recibida')
        cambios = cambios_de(cantidades, 'cantidad_despachada', 'cantidad_recibida')
        if cambios and len(comentario) < 3:
            raise ErrorTraslado("Lo recibido no coincide con lo despachado: describe la diferencia en las observaciones.")
        for l, n in cantidades.items():
            l.cantidad_recibida = n
        fijar_estado(d, 'recibido_con_diferencias' if cambios else 'recibido')
        for c in cambios:
            c['despues']['diferencia'] = c['despues']['cantidad_recibida'] - c['antes']['cantidad_despachada']
        registrar_evento(d, d.estado, usuario, anterior, despues={'unidades_recibidas': sum(cantidades.values())},
                         comentario=comentario, articulos=cambios)
    elif accion == 'cerrar':
        if d.estado == 'recibido_con_diferencias' and len(comentario) < 3:
            raise ErrorTraslado("Para cerrar un traslado con diferencias, registra cómo se concilió.")
        fijar_estado(d, 'cerrado')
        registrar_evento(d, 'cerrado', usuario, anterior, comentario=comentario)
    tocar(d)


def respuesta_error_traslado(e, d=None):
    db.session.rollback()
    cuerpo = {'success': False, 'error': str(e)}
    if d is not None and e.status == 409:
        # El cliente recibe el estado real para no mostrar algo que contradiga al servidor.
        cuerpo['traslado'] = serializar_documento(db.session.get(DocumentoTraslado, d.id), usuario_actual()[1], detalle=True)
    return jsonify(cuerpo), e.status


def obtener_documento(id_):
    d = db.session.get(DocumentoTraslado, id_)
    if d is None:
        raise ErrorTraslado(f"El traslado TR-{id_:05d} no existe.", 404)
    return d


# Agregados de los artículos vigentes de cada documento, para ordenar la bandeja.
LINEAS_DEL_DOCUMENTO = and_(Traslado.documento_id == DocumentoTraslado.id, Traslado.retirado_en.is_(None))
ORDEN_ABC = case((Traslado.clasificacion_abc == 'A', 0), (Traslado.clasificacion_abc == 'B', 1),
                 (Traslado.clasificacion_abc == 'C', 2), else_=3)


def agregado_lineas(expresion):
    return db.select(expresion).where(LINEAS_DEL_DOCUMENTO).correlate(DocumentoTraslado).scalar_subquery()


MEJOR_ABC = agregado_lineas(func.min(ORDEN_ABC))
MENOR_COBERTURA = agregado_lineas(func.coalesce(func.min(Traslado.cobertura_dias), 1e9))
TOTAL_UNIDADES = agregado_lineas(func.sum(func.coalesce(
    Traslado.cantidad_recibida, Traslado.cantidad_despachada, Traslado.cantidad_aprobada, Traslado.cantidad_sugerida)))
ORDEN_ESTADO = case(*[(DocumentoTraslado.estado == e, i) for i, e in enumerate(ESTADOS_TRASLADO)], else_=99)
ORDENES = {
    # Prioridad: el artículo de mayor clase ABC y luego la cobertura más baja del destino.
    'prioridad': [MEJOR_ABC, MENOR_COBERTURA, DocumentoTraslado.id],
    'estado': [ORDEN_ESTADO, MEJOR_ABC, DocumentoTraslado.id],
    'cantidad': [TOTAL_UNIDADES.desc(), DocumentoTraslado.id],
    'reciente': [DocumentoTraslado.actualizado_en.desc(), DocumentoTraslado.id.desc()],
    'ruta': [DocumentoTraslado.destino, DocumentoTraslado.origen, DocumentoTraslado.id],
}


def con_lineas(*condiciones):
    return DocumentoTraslado.lineas.any(and_(Traslado.retirado_en.is_(None), *condiciones))


def filtrar_documentos(args):
    q = DocumentoTraslado.query
    for campo in ('origen', 'destino', 'tipo'):
        if args.get(campo):
            q = q.filter(getattr(DocumentoTraslado, campo) == args[campo])
    if args.get('abc'):
        q = q.filter(con_lineas(Traslado.clasificacion_abc == args['abc'].upper()))
    if args.get('sucursal'):
        q = q.filter(or_(DocumentoTraslado.origen == args['sucursal'], DocumentoTraslado.destino == args['sucursal']))
    termino = texto(args.get('q')).lower()
    if termino:
        condiciones = [con_lineas(or_(func.lower(Traslado.articulo_nombre).like(f'%{termino}%'),
                                      func.lower(Traslado.articulo_codigo).like(f'%{termino}%')))]
        coincidencia_folio = re.fullmatch(r'(?:tr-?)?0*(\d+)', termino)
        if coincidencia_folio:
            condiciones.append(DocumentoTraslado.id == int(coincidencia_folio.group(1)))
        q = q.filter(or_(*condiciones))
    return q


@app.route('/api/traslados', methods=['GET'])
def listar_traslados():
    """Bandeja de documentos de traslado con filtros, orden y paginación; conteos por pestaña con los mismos filtros."""
    rol = usuario_actual()[1]
    grupo = request.args.get('grupo', 'activos')
    if grupo not in GRUPOS_ESTADO:
        return jsonify(success=False, error=f"grupo inválido. Opciones: {', '.join(GRUPOS_ESTADO)}."), 400
    orden = request.args.get('orden', 'prioridad')
    por_pagina = min(max(request.args.get('por_pagina', default=25, type=int), 1), 100)

    base = filtrar_documentos(request.args)
    por_estado = dict(base.with_entities(DocumentoTraslado.estado, func.count()).group_by(DocumentoTraslado.estado).all())
    conteos = {g: sum(por_estado.get(e, 0) for e in estados) for g, estados in GRUPOS_ESTADO.items()}

    consulta = base.filter(DocumentoTraslado.estado.in_(GRUPOS_ESTADO[grupo])).order_by(*ORDENES.get(orden, ORDENES['prioridad']))
    total = consulta.count()
    paginas = max((total + por_pagina - 1) // por_pagina, 1)
    # Si la página pedida dejó de existir (p. ej. tras aprobar el último de ella), se devuelve la última válida.
    pagina = min(max(request.args.get('pagina', default=1, type=int), 1), paginas)
    items = consulta.offset((pagina - 1) * por_pagina).limit(por_pagina).all()

    return jsonify(
        success=True, items=[serializar_documento(d, rol) for d in items], total=total, pagina=pagina,
        paginas=paginas, por_pagina=por_pagina, conteos=conteos,
        opciones={
            'origenes': sorted(o for (o,) in db.session.query(DocumentoTraslado.origen).distinct()),
            'destinos': sorted(d for (d,) in db.session.query(DocumentoTraslado.destino).distinct()),
        },
    )


@app.route('/api/traslados/<int:id_>', methods=['GET'])
def detalle_traslado(id_):
    try:
        d = obtener_documento(id_)
    except ErrorTraslado as e:
        return respuesta_error_traslado(e)
    return jsonify(success=True, traslado=serializar_documento(d, usuario_actual()[1], detalle=True))


@app.route('/api/traslados/<int:id_>', methods=['PATCH'])
def editar_traslado(id_):
    """{"version": 3, "lineas": [{"id": 8, "cantidad_sugerida": 20}], "observaciones": "..."}

    Las cantidades solo se ajustan en borrador; cada cambio queda en el historial del documento.
    """
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    d = None
    try:
        d = obtener_documento(id_)
        verificar_version(d, datos)
        cambios = False
        if datos.get('lineas'):
            if d.estado != 'borrador':
                raise ErrorTraslado("Las cantidades solo se pueden editar mientras el traslado es un borrador.", 409)
            vigentes = {l.id: l for l in lineas_vigentes(d)}
            modificados = []
            for item in datos['lineas']:
                l = vigentes.get(entero((item or {}).get('id'), 'El artículo', 1))
                if l is None:
                    raise ErrorTraslado(f"{folio(d)} no contiene ese artículo.")
                cantidad = entero(item.get('cantidad_sugerida'), f"La cantidad de {l.articulo_nombre}", 1)
                if cantidad != l.cantidad_sugerida:
                    validar_disponible(l, cantidad)
                    modificados.append(ref_articulo(l, {'cantidad_sugerida': l.cantidad_sugerida}, {'cantidad_sugerida': cantidad}))
                    l.cantidad_sugerida = cantidad
            if modificados:
                registrar_evento(d, 'cantidad_modificada', usuario, d.estado, comentario=texto(datos.get('comentario')),
                                 articulos=modificados)
                cambios = True
        if 'observaciones' in datos:
            nuevas = texto(datos['observaciones']) or None
            if nuevas != d.observaciones:
                registrar_evento(d, 'observaciones', usuario, d.estado,
                                 antes={'observaciones': d.observaciones}, despues={'observaciones': nuevas})
                d.observaciones = nuevas
                cambios = True
        if cambios:
            tocar(d)
            db.session.commit()
    except ErrorTraslado as e:
        return respuesta_error_traslado(e, d)
    return jsonify(success=True, traslado=serializar_documento(d, usuario[1], detalle=True))


@app.route('/api/traslados/<int:id_>/lineas/<int:linea_id>', methods=['DELETE'])
def retirar_articulo(id_, linea_id):
    """Quita un artículo del documento sin afectar al resto; queda registrado en el historial."""
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    d = None
    try:
        d = obtener_documento(id_)
        verificar_version(d, datos)
        if not puede_retirar(d, usuario[1]):
            raise ErrorTraslado(
                f"No se pueden quitar artículos de {folio(d)} porque está «{ESTADOS_TRASLADO[d.estado]}».", 409)
        vigentes = lineas_vigentes(d)
        l = next((x for x in vigentes if x.id == linea_id), None)
        if l is None:
            raise ErrorTraslado(f"{folio(d)} no contiene ese artículo.", 404)
        if len(vigentes) == 1:
            raise ErrorTraslado("Es el único artículo del documento: descarta o rechaza el traslado completo.")
        l.retirado_en = datetime.now()
        l.estado = 'descartado'
        registrar_evento(d, 'articulo_retirado', usuario, d.estado, comentario=texto(datos.get('comentario')),
                         articulos=[ref_articulo(l, {'cantidad_sugerida': l.cantidad_sugerida})])
        tocar(d)
        db.session.commit()
    except ErrorTraslado as e:
        return respuesta_error_traslado(e, d)
    return jsonify(success=True, traslado=serializar_documento(d, usuario[1], detalle=True))


@app.route('/api/traslados/<int:id_>/acciones', methods=['POST'])
def accion_traslado(id_):
    """{"accion": "aprobar", "version": 3, "cantidades": {"8": 10}, "motivo": "...", "comentario": "..."}"""
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    d = None
    try:
        d = obtener_documento(id_)
        verificar_version(d, datos)
        aplicar_accion(d, datos.get('accion'), datos, usuario)
        db.session.commit()
    except ErrorTraslado as e:
        return respuesta_error_traslado(e, d)
    return jsonify(success=True, traslado=serializar_documento(d, usuario[1], detalle=True))


ACCIONES_EN_LOTE = ['enviar', 'descartar']  # aprobar y rechazar exigen revisión individual


@app.route('/api/traslados/lote', methods=['POST'])
def accion_lote():
    """{"accion": "enviar", "items": [{"id": 1, "version": 2}, ...]}: todo o nada."""
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    accion, items = datos.get('accion'), datos.get('items') or []
    if accion not in ACCIONES_EN_LOTE:
        return jsonify(success=False, error="Por lote solo se puede enviar a aprobación o descartar borradores."), 400
    if not isinstance(items, list) or not items:
        return jsonify(success=False, error="No se indicaron traslados."), 400

    errores, procesados = [], []
    for item in items:
        try:
            d = obtener_documento(entero(item.get('id'), 'El id', 1))
            verificar_version(d, item)
            aplicar_accion(d, accion, item, usuario)
            procesados.append(d)
        except ErrorTraslado as e:
            errores.append({'id': item.get('id'), 'error': str(e)})
    if errores:
        db.session.rollback()
        return jsonify(success=False, error=f"No se aplicó ningún cambio: {len(errores)} de {len(items)} traslados no lo permiten.",
                       errores=errores), 409
    db.session.commit()
    return jsonify(success=True, traslados=[serializar_documento(d, usuario[1]) for d in procesados])


def documento_borrador(tipo, origen, destino, usuario, ahora, horizonte=None):
    """Borrador abierto de la ruta al que se agregan artículos nuevos; si no hay, se crea uno."""
    d = DocumentoTraslado.query.filter_by(tipo=tipo, origen=origen, destino=destino, estado='borrador').first()
    if d is not None:
        return d, False
    d = DocumentoTraslado(tipo=tipo, origen=origen, destino=destino, estado='borrador', horizonte_dias=horizonte,
                          creado_por=usuario[0], creado_en=ahora, actualizado_en=ahora)
    db.session.add(d)
    db.session.flush()
    return d, True


def registrar_alta(d, nuevo, lineas, usuario, comentario):
    """Evento de creación del documento o de artículos agregados a un borrador existente."""
    articulos = [ref_articulo(l, despues={'cantidad_sugerida': l.cantidad_sugerida}) for l in lineas]
    if nuevo:
        registrar_evento(d, 'creado', usuario, despues={'articulos': len(lineas),
                                                        'unidades': sum(l.cantidad_sugerida for l in lineas)},
                         comentario=comentario, articulos=articulos)
    else:
        registrar_evento(d, 'articulos_agregados', usuario, d.estado, comentario=comentario, articulos=articulos)
        tocar(d)


@app.route('/api/traslados/generar', methods=['POST'])
def generar_traslados():
    """Convierte las sugerencias actuales en un borrador por sucursal, sin duplicar artículos con un traslado abierto.

    {"dias": 15, "clases": ["A"]}: sin clases se proponen artículos de todas las clases ABC.
    """
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    try:
        dias = entero(datos.get('dias', 15), 'El horizonte', 1)
        clases = datos.get('clases') or ['A', 'B', 'C']
        if not isinstance(clases, list) or not set(clases) <= {'A', 'B', 'C'}:
            raise ErrorTraslado("Las clases ABC deben ser una lista con A, B o C.")
    except ErrorTraslado as e:
        return respuesta_error_traslado(e)

    abiertos = Traslado.query.filter(Traslado.estado.in_(ESTADOS_ABIERTOS)).all()
    ocupados = {(t.articulo_codigo, t.origen, t.destino) for t in abiertos}
    comprometido = {}
    for t in abiertos:
        if t.origen == ALMACEN and t.estado in ESTADOS_COMPROMETEN_ORIGEN:
            comprometido[t.articulo_codigo] = comprometido.get(t.articulo_codigo, 0) + (
                t.cantidad_aprobada if t.cantidad_aprobada is not None else t.cantidad_sugerida)

    # El reparto del almacén entre sucursales es por artículo, así que filtrar por clase no altera las cantidades.
    sugerencias = [s for s in calcular_sugerencias_traslado(dias, comprometido) if s['clasificacion_abc'] in clases]
    por_destino = {}
    for s in sugerencias:
        if (s['codigo'], ALMACEN, s['sucursal']) not in ocupados:
            por_destino.setdefault(s['sucursal'], []).append(s)

    ahora = datetime.now()
    creados = documentos = 0
    for destino, items in por_destino.items():
        d, nuevo = documento_borrador('reposicion', ALMACEN, destino, usuario, ahora, dias)
        lineas = [Traslado(
            articulo_codigo=s['codigo'], articulo_nombre=s['nombre'], clasificacion_abc=s['clasificacion_abc'],
            tipo='reposicion', origen=ALMACEN, destino=destino, estado='borrador',
            cantidad_sugerida=s['cantidad'], stock_origen=s['disponible_almacen'], stock_destino=s['stock_sucursal'],
            cobertura_dias=s['cobertura_dias'], horizonte_dias=dias, creado_por=usuario[0],
            creado_en=ahora, actualizado_en=ahora,
        ) for s in items]
        d.lineas.extend(lineas)
        db.session.flush()
        registrar_alta(d, nuevo, lineas, usuario, f"Propuesta generada para cubrir {dias} días de demanda.")
        creados += len(lineas)
        documentos += 1
    db.session.commit()
    omitidos = len(sugerencias) - creados
    return jsonify(success=True, creados=creados, documentos=documentos, omitidos=omitidos, sugerencias=len(sugerencias),
                   message=(f"Se agregaron {creados} artículos ({'clase' if len(clases) == 1 else 'clases'} "
                            f"{', '.join(sorted(clases))}) en {documentos} "
                            f"{'documento' if documentos == 1 else 'documentos'} de traslado." +
                            (f" {omitidos} sugerencias ya tenían un traslado abierto." if omitidos else "")))


@app.route('/api/traslados', methods=['POST'])
def crear_retorno():
    """Retorno de mercancía de una sucursal al almacén principal (p. ej. mercancía estancada).

    Se agrega al borrador de retorno abierto de esa sucursal o crea uno nuevo.
    """
    datos = request.get_json(silent=True) or {}
    usuario = usuario_actual()
    try:
        codigo = texto(datos.get('articulo_codigo'))
        origen = texto(datos.get('origen'))
        art = db.session.get(Articulo, codigo) if codigo else None
        if art is None:
            raise ErrorTraslado("El artículo no existe.")
        if not origen or origen == ALMACEN:
            raise ErrorTraslado("Indica la sucursal desde la que se retorna la mercancía.")
        cantidad = entero(datos.get('cantidad'), 'La cantidad', 1)
        if Traslado.query.filter(Traslado.articulo_codigo == codigo, Traslado.origen == origen,
                                 Traslado.destino == ALMACEN, Traslado.estado.in_(ESTADOS_ABIERTOS)).first():
            raise ErrorTraslado(f"Ya hay un retorno abierto de este artículo desde {origen}.", 409)
        ahora = datetime.now()
        t = Traslado(
            articulo_codigo=codigo, articulo_nombre=art.nombre, clasificacion_abc=clasificacion_abc().get(codigo, 'C'),
            tipo='retorno', origen=origen, destino=ALMACEN, estado='borrador', cantidad_sugerida=cantidad,
            stock_origen=stock_en(origen, codigo), stock_destino=stock_en(ALMACEN, codigo),
            creado_por=usuario[0], creado_en=ahora, actualizado_en=ahora,
        )
        validar_disponible(t, cantidad)
        d, nuevo = documento_borrador('retorno', origen, ALMACEN, usuario, ahora)
        d.lineas.append(t)
        db.session.flush()
        registrar_alta(d, nuevo, [t], usuario, texto(datos.get('comentario')) or "Retorno de mercancía estancada al almacén.")
        db.session.commit()
    except ErrorTraslado as e:
        return respuesta_error_traslado(e)
    return jsonify(success=True, traslado=serializar_documento(d, usuario[1], detalle=True)), 201


# ==================== CENTRO DE DECISIONES ====================
# Cobertura (días de venta que cubre el stock) por debajo de la cual un artículo A o B se considera crítico.
# Es un parámetro operativo provisional: ajustarlo cuando se defina la regla real de la empresa.
DIAS_COBERTURA_CRITICA = 7


def productos_criticos(sucursal=None, dias=DIAS_COBERTURA_CRITICA):
    """Artículos A y B cuyo stock en una sucursal cubre menos de `dias` de su venta diaria.

    Solo se evalúan pares artículo-sucursal presentes en el inventario cargado: sin inventario no hay certeza
    de que el stock sea cero y no se genera la alerta.
    """
    stock_almacen, stock_sucursal, _, vpd_sucursal, _ = datos_demanda()
    abc = clasificacion_abc()
    nombres = dict(db.session.query(Articulo.codigo, Articulo.nombre).all())
    abiertos = {(t.articulo_codigo, t.destino): t for t in Traslado.query.filter(
        Traslado.estado.in_(ESTADOS_ABIERTOS), Traslado.origen == ALMACEN)}
    items = []
    for (codigo, suc), stock in stock_sucursal.items():
        if (sucursal and suc != sucursal) or codigo not in nombres or abc.get(codigo) not in ('A', 'B'):
            continue
        vpd = vpd_sucursal.get((codigo, suc), 0)
        if vpd <= 0:
            continue
        cobertura = max(stock, 0) / vpd
        if cobertura >= dias:
            continue
        t = abiertos.get((codigo, suc))
        items.append({
            'codigo': codigo, 'nombre': nombres[codigo], 'sucursal': suc, 'clasificacion_abc': abc[codigo],
            'stock': stock, 'venta_diaria': round(vpd, 2), 'cobertura_dias': round(cobertura, 1),
            'stock_almacen': stock_almacen.get(codigo, 0),
            'traslado': {'id': t.documento_id, 'folio': folio(t.documento), 'estado': t.estado} if t else None,
        })
    items.sort(key=lambda i: (i['clasificacion_abc'], i['cobertura_dias'], i['nombre']))
    return items


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

    criticos = productos_criticos(sucursal)
    capital = calcular_capital_estancado(90, sucursal)
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


@app.route('/api/inventario/criticos', methods=['GET'])
def listar_criticos():
    sucursal = texto(request.args.get('sucursal')) or None
    dias = request.args.get('dias', default=DIAS_COBERTURA_CRITICA, type=int)
    return jsonify(success=True, dias_cobertura=dias, items=productos_criticos(sucursal, dias))


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
    abc = clasificacion_abc()
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
            raise ErrorTraslado("El artículo no existe.")
        if not sucursal:
            raise ErrorTraslado("Indica la ubicación donde se contó la mercancía.")
        contada = entero(datos.get('existencia_contada'), 'La cantidad contada', 0)
        sistema = stock_en(sucursal, codigo)
        if contada == sistema:
            raise ErrorTraslado(f"Lo contado coincide con el sistema ({sistema} u): no hay discrepancia que reportar.")
        comentario = texto(datos.get('comentario'))
        if len(comentario) < 3:
            raise ErrorTraslado("Describe brevemente la discrepancia.")
        if Discrepancia.query.filter_by(articulo_codigo=codigo, sucursal=sucursal, estado='pendiente').first():
            raise ErrorTraslado("Ya hay una discrepancia pendiente de revisión para este artículo en esa ubicación.", 409)
    except ErrorTraslado as e:
        return jsonify(success=False, error=str(e)), e.status
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
    ('traslados', 'documento_id', 'INTEGER REFERENCES traslado_documentos(id)'),
    ('traslados', 'retirado_en', 'TIMESTAMP'),
    ('inventarios', 'precio_usd', 'NUMERIC(12,4)'),
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
    agrupar_traslados_en_documentos()


def agrupar_traslados_en_documentos():
    """Traslados creados antes de los documentos (uno por artículo): se agrupan en documentos TR por ruta.

    Los abiertos se agrupan por ruta y estado para poder seguir operándolos juntos; los finalizados, además, por
    día de creación para no mezclar operaciones históricas distintas. Su historial se copia al documento.
    """
    sueltos = Traslado.query.filter(Traslado.documento_id.is_(None)).order_by(Traslado.id).all()
    if not sueltos:
        return
    grupos = {}
    for t in sueltos:
        clave = (t.tipo, t.origen, t.destino, t.estado)
        if t.estado not in ESTADOS_ABIERTOS:
            clave += (t.creado_en.date(),)
        grupos.setdefault(clave, []).append(t)
    for lineas in grupos.values():
        primera = lineas[0]
        unicos = lambda campo: '; '.join(dict.fromkeys(getattr(l, campo) for l in lineas if getattr(l, campo))) or None
        d = DocumentoTraslado(
            tipo=primera.tipo, origen=primera.origen, destino=primera.destino, estado=primera.estado,
            horizonte_dias=primera.horizonte_dias, motivo_rechazo=unicos('motivo_rechazo'),
            observaciones=unicos('observaciones'), creado_por=primera.creado_por,
            creado_en=min(l.creado_en for l in lineas), actualizado_en=max(l.actualizado_en for l in lineas),
        )
        db.session.add(d)
        d.lineas.extend(lineas)
        db.session.flush()
        por_id = {l.id: l for l in lineas}
        for e in EventoTraslado.query.filter(EventoTraslado.traslado_id.in_(por_id)).order_by(EventoTraslado.fecha, EventoTraslado.id):
            detalle = json.loads(e.detalle) if e.detalle else {}
            detalle['articulos'] = [ref_articulo(por_id[e.traslado_id])]
            db.session.add(EventoDocumento(documento_id=d.id, tipo=e.tipo, estado_anterior=e.estado_anterior,
                                           estado_nuevo=e.estado_nuevo, usuario=e.usuario, rol=e.rol, fecha=e.fecha,
                                           detalle=json.dumps(detalle, ensure_ascii=False)))
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrar_esquema()
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
