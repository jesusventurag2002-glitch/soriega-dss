"""Reglas de ventas: excepciones (ventas que no son facturación comercial), rentabilidad por sucursal y grupo, y
lectura de tasas cambiarias escritas a mano."""
import re
from datetime import timedelta

from dominio.comun import numero, parsear_fecha
from dominio.errores import ErrorDominio

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
IDS_EXCEPCION = {e['id'] for e in EXCEPCIONES}
GRUPOS_PRINCIPALES = 5  # el resto se agrupa en "OTROS" para que el desglose sea legible


def excepciones_configuradas(guardadas):
    """Ids excluidos según "Administrar excepciones" ({id: excluida}); sin fila, el valor por defecto de la hoja ANAL."""
    return [e['id'] for e in EXCEPCIONES if guardadas.get(e['id'], e.get('por_defecto', True))]


def excluir_de_parametro(valor):
    """?excluir=id1,id2 (vacío = facturación bruta): solo los ids conocidos."""
    return [x for x in valor.split(',') if x in IDS_EXCEPCION]


def validar_seleccion(excluir):
    if not isinstance(excluir, list) or not set(excluir) <= IDS_EXCEPCION:
        raise ErrorDominio("'excluir' debe ser una lista de ids de excepción válidos.")
    return {id_: id_ in excluir for id_ in IDS_EXCEPCION}


def rentabilidad(nombre, total, costo, venta_sin_costo):
    """Utilidad = ventas - costo (ambos con IVA, como en la hoja ANAL); margen sobre ventas."""
    utilidad = total - costo
    return {'grupo': nombre, 'total': round(total, 2), 'costo': round(costo, 2), 'utilidad': round(utilidad, 2),
            'margen': round(utilidad / total * 100, 1) if total else None, 'ventas_sin_costo': round(venta_sin_costo, 2)}


def analisis_por_sucursal(filas):
    """filas: [(sucursal, grupo, total, costo, ventas sin costo)] del mes.

    Devuelve (grupos principales, sucursales ordenadas por venta): cada sucursal trae los principales con el resto en
    OTROS (para el gráfico) y todos los grupos (para la tabla).
    """
    total_por_grupo = {}
    for _, grupo, total, _, _ in filas:
        total_por_grupo[grupo] = total_por_grupo.get(grupo, 0) + float(total or 0)
    principales = sorted(total_por_grupo, key=total_por_grupo.get, reverse=True)[:GRUPOS_PRINCIPALES]

    por_sucursal, todos = {}, {}
    for sucursal, grupo, total, costo, venta_sin_costo in filas:
        valores = (float(total or 0), float(costo or 0), float(venta_sin_costo or 0))
        for destino, clave in ((por_sucursal, grupo if grupo in principales else 'OTROS'), (todos, grupo)):
            actual = destino.setdefault(sucursal, {}).get(clave, (0, 0, 0))
            destino[sucursal][clave] = tuple(a + b for a, b in zip(actual, valores))

    def resumen(sucursal):
        grupos, completos = por_sucursal[sucursal], todos[sucursal]
        datos = rentabilidad(None, *(sum(v[i] for v in grupos.values()) for i in range(3)))
        del datos['grupo']
        return {
            'sucursal': sucursal, **datos,
            # Orden fijo (principales y luego OTROS) para que cada grupo conserve su color y posición.
            'grupos': [rentabilidad(g, *grupos[g]) for g in principales + ['OTROS'] if g in grupos],
            'todos_los_grupos': sorted((rentabilidad(g, *v) for g, v in completos.items()), key=lambda g: g['total'], reverse=True),
        }

    return principales, sorted((resumen(s) for s in por_sucursal), key=lambda s: s['total'], reverse=True)


def ultimos_dias(corte, diarios, dias=7):
    """Serie diaria que termina en `corte`, con 0 en los días sin ventas. diarios: {fecha: total}."""
    desde = corte - timedelta(days=dias - 1)
    return [{'fecha': (desde + timedelta(days=i)).isoformat(), 'total': round(float(diarios.get(desde + timedelta(days=i), 0)), 2)}
            for i in range(dias)]


def leer_lista_tasas(texto):
    """"2026-10-01 36,50\\n02/10/2026 36,75" -> [(fecha, tasa)]; las líneas que no se entienden se ignoran."""
    tasas = []
    for linea in texto.splitlines():
        partes = re.split(r'[\t,\s]+', linea.strip(), maxsplit=1)
        if len(partes) < 2:
            continue
        fecha, tasa = parsear_fecha(partes[0]), numero(partes[1], None)
        if fecha is not None and tasa is not None:
            tasas.append((fecha, tasa))
    return tasas
