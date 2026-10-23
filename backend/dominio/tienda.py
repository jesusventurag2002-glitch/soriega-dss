"""Piso de venta: existencias por ubicación y discrepancias entre lo contado y el sistema."""
from datetime import datetime

from dominio.comun import texto
from dominio.errores import Conflicto, ErrorDominio
from dominio.traslados import ALMACEN


def existencias_por_ubicacion(filas):
    """[(código, origen 'INV'|'INVAL', sucursal, total, precio)] -> {código: [(ubicación, existencia, precio USD)]},
    con el almacén principal primero y luego las sucursales por nombre."""
    por_codigo = {}
    for codigo, origen, sucursal, total, precio in filas:
        ubicacion = ALMACEN if origen == 'INVAL' else (sucursal or 'Sin asignar')
        existencia, _ = por_codigo.setdefault(codigo, {}).get(ubicacion, (0, None))
        por_codigo[codigo][ubicacion] = (existencia + int(total or 0), float(precio) if precio else None)
    return {c: [(u, n, p) for u, (n, p) in sorted(ubicaciones.items(), key=lambda x: (x[0] != ALMACEN, x[0]))]
            for c, ubicaciones in por_codigo.items()}


def validar_conteo(contada, sistema, comentario):
    if contada == sistema:
        raise ErrorDominio(f"Lo contado coincide con el sistema ({sistema} u): no hay discrepancia que reportar.")
    if len(comentario) < 3:
        raise ErrorDominio("Describe brevemente la discrepancia.")


def revisar_discrepancia(d, datos, usuario):
    """{"resolucion": "..."}: la marca como revisada; solo una vez."""
    if d.estado != 'pendiente':
        raise Conflicto("La discrepancia ya fue revisada.")
    resolucion = texto(datos.get('resolucion'))
    if len(resolucion) < 3:
        raise ErrorDominio("Indica qué se hizo con la discrepancia.")
    d.estado, d.resolucion = 'revisada', resolucion
    d.revisado_por, d.revisado_en = usuario[0], datetime.now()
