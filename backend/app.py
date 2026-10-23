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
from adaptadores.entrada.traslados import crear_blueprint as blueprint_traslados, resumen_documento, serializar_evento
from adaptadores.salida.migraciones import agrupar_traslados_en_documentos, migrar_esquema  # noqa: F401 (pruebas)
from adaptadores.salida.repo_demanda import RepositorioDemandaSQL
from adaptadores.salida.repo_inventario import InventarioSQL
from adaptadores.salida.repo_ventas import RepositorioVentasSQL
from adaptadores.salida.repo_traslados import ORDENES, RepositorioTrasladosSQL
from aplicacion.demanda import CasosDemanda
from aplicacion.traslados import CasosTraslados
from aplicacion.ventas import CasosVentas
from dominio.comun import entero, numero, parsear_fecha
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


# ==================== UTILIDADES DE PARSEO ====================
TIPOS_REPORTE = {'ventas', 'inv_fisico', 'inv_inval', 'tasas'}

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


def codigo_articulo(valor):
    # Excel suele entregar los códigos como float (12345.0)
    return texto(valor).split('.')[0].strip()


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


@app.route('/api/capital_estancado', methods=['GET'])
def capital_estancado():
    dias_min = request.args.get('dias_min', default=90, type=int)
    limite = request.args.get('limite', default=100, type=int)
    datos = casos_demanda.capital_estancado(dias_min, texto(request.args.get('sucursal')) or None)
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


# ==================== CENTRO DE DECISIONES ====================
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

    criticos = casos_demanda.productos_criticos(sucursal)
    capital = casos_demanda.capital_estancado(90, sucursal)
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
    abc = casos_demanda.clasificacion_abc()
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
            raise ErrorDominio("El artículo no existe.")
        if not sucursal:
            raise ErrorDominio("Indica la ubicación donde se contó la mercancía.")
        contada = entero(datos.get('existencia_contada'), 'La cantidad contada', 0)
        sistema = inventario.stock_en(sucursal, codigo)
        if contada == sistema:
            raise ErrorDominio(f"Lo contado coincide con el sistema ({sistema} u): no hay discrepancia que reportar.")
        comentario = texto(datos.get('comentario'))
        if len(comentario) < 3:
            raise ErrorDominio("Describe brevemente la discrepancia.")
        if Discrepancia.query.filter_by(articulo_codigo=codigo, sucursal=sucursal, estado='pendiente').first():
            raise Conflicto("Ya hay una discrepancia pendiente de revisión para este artículo en esa ubicación.")
    except ErrorDominio as e:
        return jsonify(success=False, error=str(e)), estado_http(e)
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrar_esquema()
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG') == '1', use_reloader=False)
