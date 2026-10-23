"""Interpretación de los reportes del sistema administrativo: filas de ventas, inventario y tasas.

Las filas llegan como diccionarios con los encabezados en minúsculas y None en las celdas vacías.
"""
import unicodedata

from dominio.comun import numero, parsear_fecha, texto
from dominio.errores import ErrorDominio
from dominio.ventas import EXCEPCIONES

TIPOS_REPORTE = {'ventas', 'inv_fisico', 'inv_inval', 'tasas'}
# Los reportes de ventas y de inventario de sucursal no traen la sucursal: se indica al cargar.
REQUIEREN_SUCURSAL = ('ventas', 'inv_fisico')
# Artículos de uso interno (no comerciales): se ignoran en toda la lógica de negocio.
GRUPOS_EXCLUIDOS = ["MARKETING"]
SUBGRUPOS_EXCLUIDOS = ["EQUIPOS DE OFICINA"]
IVA = 1.16


def codigo_articulo(valor):
    # Excel suele entregar los códigos como float (12345.0)
    return texto(valor).split('.')[0].strip()


def grupo_de(row):
    return texto(row.get('nombredegr', row.get('nombredegrupo'))).upper()


def es_articulo_excluido(row):
    return grupo_de(row) in GRUPOS_EXCLUIDOS or texto(row.get('nombre_sub')).upper() in SUBGRUPOS_EXCLUIDOS


def precio_venta_usd(row, origen):
    """Precio de venta en USD sin IVA. Las sucursales lo traen en PRECIO1EX (PRECIO1 está en Bs); el almacén
    principal trabaja en USD y lo trae en PRECIO1, con PRECIO1EX vacío."""
    precio = numero(row.get('precio1ex'))
    if precio <= 0 and origen == 'INVAL':
        precio = numero(row.get('precio1'))
    return round(precio, 4) if precio > 0 else None


def detectar_excepcion(row):
    valores = {'nombrecli': texto(row.get('nombrecli')).upper(), 'nombredegr': grupo_de(row),
               'nombre': texto(row.get('nombre')).upper()}
    return next((e['id'] for e in EXCEPCIONES if valores[e['campo']] == e['valor']), None)


def ventas_desde_filas(filas, sucursal):
    """Ventas del reporte con sus montos calculados. Devuelve (ventas, tasas BCV por fecha, conteos)."""
    tiene_fact = bool(filas) and 'fact' in filas[0]
    tiene_costo = bool(filas) and 'costo' in filas[0]
    ventas, tasas_bcv = [], {}  # FACTOR del reporte = tasa BCV del día
    conteos = {'internas': 0, 'sin_fecha': 0, 'por_excepcion': {}}

    for row in filas:
        codigo = codigo_articulo(row.get('codigo', row.get('cdg')))
        if not codigo or codigo == 'nan':
            continue
        if es_articulo_excluido(row):
            conteos['internas'] += 1
            continue
        excepcion = detectar_excepcion(row)
        if excepcion:
            conteos['por_excepcion'][excepcion] = conteos['por_excepcion'].get(excepcion, 0) + 1
        fecha_emision = parsear_fecha(row.get('emision'))
        if fecha_emision is None:
            conteos['sin_fecha'] += 1
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
            factura_bs, factura_real = None, numero(row.get('fact'))
        else:
            factura_bs = (precio_local * IVA) * cantidad_neta
            factura_real = factura_bs / f_sistema
        costo_real = numero(row.get('costo')) if tiene_costo else (numero(row.get('costoex')) * IVA) * cantidad_neta

        ventas.append(dict(
            documento=texto(row.get('documento'), 'S/D'), articulo_codigo=codigo,
            nombre_articulo=texto(row.get('nombre'), 'Artículo'), grupo_venta=grupo_venta,
            cantidad_neta=cantidad_neta, precio_fin_moneda_local=precio_local,
            factor_sistema=f_sistema, factura_real_usd=factura_real,
            costo_real_usd=costo_real, utilidad_real_usd=factura_real - costo_real,
            fecha_emision=fecha_emision, sucursal=sucursal, factura_bs=factura_bs, excepcion=excepcion,
        ))
    return ventas, tasas_bcv, conteos


def mensaje_ventas(sucursal, ventas, tasas_bcv, conteos):
    mensaje = f"Historial de ventas de {sucursal} cargado: {len(ventas)} registros."
    por_excepcion = conteos['por_excepcion']
    if por_excepcion:
        nombres = {e['id']: e['nombre'] for e in EXCEPCIONES}
        mensaje += (f" {sum(por_excepcion.values())} marcados como excepción y excluibles en el análisis ("
                    + ', '.join(f"{nombres[k]}: {n}" for k, n in sorted(por_excepcion.items(), key=lambda x: -x[1])) + ").")
    if tasas_bcv:
        mensaje += f" Tasa BCV registrada para {len(tasas_bcv)} días."
    if conteos['internas']:
        mensaje += f" {conteos['internas']} ignorados por ser de uso interno (Marketing / Equipos de oficina)."
    if conteos['sin_fecha']:
        mensaje += f" {conteos['sin_fecha']} omitidos por fecha inválida."
    return mensaje


def tasas_desde_filas(filas):
    """Tasas internas por fecha (hoja TASA del libro de pedidos: columnas FECHA y TASA)."""
    tasas = {}
    for row in filas:
        fecha, tasa = parsear_fecha(row.get('fecha')), numero(row.get('tasa'))
        if fecha and tasa > 0:
            tasas[fecha] = tasa
    if not tasas:
        raise ErrorDominio("No se encontraron filas con FECHA y TASA válidas.")
    return tasas


def inventario_desde_filas(filas, origen, grupos_catalogo):
    """El reporte es una foto completa del inventario de una ubicación.

    grupos_catalogo: {código: grupo} de los artículos ya registrados. Devuelve:
    - articulos: {código: {'nuevo', 'nombre' (solo nuevos), 'grupo' (None = no cambia), 'costo'}}
    - existencias: {código: (existencia, precio USD)}; si un código se repite, prevalece la última fila
    - internos: códigos de uso interno a eliminar (incluye los ya guardados por cargas anteriores)
    - conteos: nuevos y actualizados (cada fila repetida cuenta como actualización)
    """
    articulos, existencias = {}, {}
    internos = {c for c, g in grupos_catalogo.items() if (g or '').upper() in GRUPOS_EXCLUIDOS}
    nuevos = actualizados = 0
    for row in filas:
        codigo = codigo_articulo(row.get('codigo', row.get('cdg', row.get('codigoart'))))
        if not codigo or codigo == 'nan':
            continue
        if es_articulo_excluido(row):
            internos.add(codigo)
            continue
        costo, grupo = numero(row.get('costoex', row.get('costo'))), grupo_de(row)
        if codigo in articulos or codigo in grupos_catalogo:
            art = articulos.setdefault(codigo, {'nuevo': False, 'grupo': None})
            art['costo'] = costo
            if grupo:
                art['grupo'] = grupo
            actualizados += 1
        else:
            articulos[codigo] = {'nuevo': True, 'nombre': texto(row.get('nombre', row.get('nombreart')), 'Sin Nombre'),
                                 'grupo': grupo or 'SIN GRUPO', 'costo': costo}
            nuevos += 1
        existencias[codigo] = (int(numero(row.get('existencia'))), precio_venta_usd(row, origen))
    return articulos, existencias, internos, {'nuevos': nuevos, 'actualizados': actualizados}


def mensaje_inventario(origen, sucursal, conteos, internos):
    destino = f"de {sucursal} (INV)" if origen == 'INV' else "del Almacén Principal (INVAL)"
    mensaje = (f"Inventario {destino} guardado: {conteos['nuevos'] + conteos['actualizados']} artículos "
               f"({conteos['nuevos']} nuevos, {conteos['actualizados']} actualizados).")
    if internos:
        mensaje += f" {len(internos)} ignorados por ser de uso interno (Marketing / Equipos de oficina)."
    return mensaje


def clave_sucursal(nombre):
    sin_acentos = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    return ' '.join(sin_acentos.lower().split())


def canonizar_sucursal(nombre, registradas):
    """Reutiliza el nombre ya registrado si coincide sin distinguir mayúsculas ni acentos ("MATURIN" -> "Maturín")."""
    nombre = ' '.join(texto(nombre).split())
    if not nombre:
        return ''
    clave = clave_sucursal(nombre)
    return next((s for s in sorted(registradas) if clave_sucursal(s) == clave), nombre.title())
