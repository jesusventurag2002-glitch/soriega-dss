"""Rotación y cobertura: clasificación ABC, venta diaria, sugerencias de traslado y de compra, productos críticos y
capital estancado. Funciones puras sobre los agregados que entrega el repositorio.

La demanda solo considera ventas comerciales (el repositorio ya excluye reposiciones entre tiendas, mermas,
consumo interno y servicios: no son rotación de mercancía).
"""
from dataclasses import dataclass

from dominio.traslados import ALMACEN, folio

SIN_SUCURSAL = 'Sin asignar'
# Cobertura (días de venta que cubre el stock) por debajo de la cual un artículo A o B se considera crítico.
# Es un parámetro operativo provisional: ajustarlo cuando se defina la regla real de la empresa.
DIAS_COBERTURA_CRITICA = 7


def clasificar_abc(unidades):
    """[(código, unidades netas vendidas)] -> {código: clase}: A = primer 80% acumulado, B = siguiente 15%, C = resto."""
    unidades = sorted(unidades, key=lambda x: -(x[1] or 0))
    total = sum(max(int(u or 0), 0) for _, u in unidades)
    abc, acumulado = {}, 0
    for codigo, u in unidades:
        participacion_previa = acumulado / total if total else 1
        abc[codigo] = 'A' if participacion_previa < 0.80 else 'B' if participacion_previa < 0.95 else 'C'
        acumulado += max(int(u or 0), 0)
    return abc


def venta_diaria(unidades, desde, hasta):
    rango_dias = (hasta - desde).days + 1 if desde else 30
    return int(unidades or 0) / (rango_dias if rango_dias > 0 else 1)


@dataclass
class Demanda:
    stock_almacen: dict   # {código: unidades}
    stock_sucursal: dict  # {(código, sucursal): unidades}
    sucursales: list      # sucursales con inventario cargado (sin él, su stock es desconocido)
    vpd_sucursal: dict    # {(código, sucursal): venta diaria}
    vpd_total: dict       # {código: venta diaria}


def demanda(existencias, ventas_por_sucursal, ventas_por_articulo):
    """existencias: [(código, origen 'INV'|'INVAL', sucursal, total)];
    ventas_por_sucursal: [(código, sucursal, unidades, desde, hasta)]; ventas_por_articulo: [(código, unidades, desde, hasta)]."""
    stock_almacen, stock_sucursal = {}, {}
    for codigo, origen, sucursal, total in existencias:
        if origen == 'INVAL':
            stock_almacen[codigo] = stock_almacen.get(codigo, 0) + int(total or 0)
        else:
            stock_sucursal[(codigo, sucursal or SIN_SUCURSAL)] = int(total or 0)
    return Demanda(
        stock_almacen, stock_sucursal, sorted({s for _, s in stock_sucursal}),
        {(codigo, sucursal or SIN_SUCURSAL): venta_diaria(u, desde, hasta)
         for codigo, sucursal, u, desde, hasta in ventas_por_sucursal},
        {codigo: venta_diaria(u, desde, hasta) for codigo, u, desde, hasta in ventas_por_articulo},
    )


def sugerencias_traslado(articulos, dem, abc, dias, comprometido_almacen=None):
    """Necesidad de cada sucursal (venta diaria * días - stock) cubierta con el stock del almacén.

    comprometido_almacen: unidades del almacén ya reservadas en traslados abiertos, que no se vuelven a repartir.
    """
    comprometido_almacen = comprometido_almacen or {}
    resultados = []
    for art in articulos:
        stock_inval = dem.stock_almacen.get(art.codigo, 0)
        if stock_inval <= 0:
            continue
        necesidades = []
        for sucursal in dem.sucursales:
            stock_suc = dem.stock_sucursal.get((art.codigo, sucursal), 0)
            vpd = dem.vpd_sucursal.get((art.codigo, sucursal), 0)
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


def reposicion(articulos, dem, abc, dias):
    """Compra sugerida: demanda proyectada de la red que no cubre el stock total (almacén + sucursales)."""
    resultados = []
    for art in articulos:
        demanda_proyectada = dem.vpd_total.get(art.codigo, 0) * dias
        stock_total = dem.stock_almacen.get(art.codigo, 0) + sum(dem.stock_sucursal.get((art.codigo, s), 0) for s in dem.sucursales)
        if stock_total < demanda_proyectada:
            cant_a_pedir = max(0, round(demanda_proyectada - stock_total))
            if cant_a_pedir > 0:
                resultados.append({
                    'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                    'proveedor': art.proveedor, 'cantidad_pedir': cant_a_pedir,
                    'deficit': round(demanda_proyectada - stock_total),
                    'clasificacion_abc': abc.get(art.codigo, 'C'),
                })
    return resultados


def productos_criticos(dem, abc, nombres, abiertas_desde_almacen, sucursal=None, dias=DIAS_COBERTURA_CRITICA):
    """Artículos A y B cuyo stock en una sucursal cubre menos de `dias` de su venta diaria.

    Solo se evalúan pares artículo-sucursal presentes en el inventario cargado: sin inventario no hay certeza
    de que el stock sea cero y no se genera la alerta.
    """
    abiertos = {(t.articulo_codigo, t.destino): t for t in abiertas_desde_almacen}
    items = []
    for (codigo, suc), stock in dem.stock_sucursal.items():
        if (sucursal and suc != sucursal) or codigo not in nombres or abc.get(codigo) not in ('A', 'B'):
            continue
        vpd = dem.vpd_sucursal.get((codigo, suc), 0)
        if vpd <= 0:
            continue
        cobertura = max(stock, 0) / vpd
        if cobertura >= dias:
            continue
        t = abiertos.get((codigo, suc))
        items.append({
            'codigo': codigo, 'nombre': nombres[codigo], 'sucursal': suc, 'clasificacion_abc': abc[codigo],
            'stock': stock, 'venta_diaria': round(vpd, 2), 'cobertura_dias': round(cobertura, 1),
            'stock_almacen': dem.stock_almacen.get(codigo, 0),
            'traslado': {'id': t.documento_id, 'folio': folio(t.documento), 'estado': t.estado} if t else None,
        })
    items.sort(key=lambda i: (i['clasificacion_abc'], i['cobertura_dias'], i['nombre']))
    return items


def capital_estancado(inicio, corte, ultima_venta, existencias, articulos, dias_min, sucursal=None):
    """Artículos con existencia y costo cuya última venta supera dias_min (o que no se vendieron en el historial).

    inicio/corte: primera y última fecha del historial de ventas (None = sin ventas: devuelve None).
    ultima_venta: {código: fecha de la última venta comercial con unidades}. existencias: como en `demanda`.
    Sin sucursal: existencia consolidada (todas las sucursales + almacén). Con sucursal (o ALMACEN): solo la de esa
    ubicación.
    """
    if corte is None:
        return None
    # Los días se cuentan hasta la última fecha del historial, no hasta hoy, porque los datos son una foto fija.
    dias_historial = (corte - inicio).days

    almacen, por_sucursal = {}, {}
    for codigo, origen, ubicacion, total in existencias:
        cantidad = max(int(total or 0), 0)
        if origen == 'INVAL':
            almacen[codigo] = almacen.get(codigo, 0) + cantidad
        elif cantidad:
            por_sucursal.setdefault(codigo, {})[ubicacion or SIN_SUCURSAL] = cantidad

    resultado = []
    for art in articulos:
        if not art.costoex or art.costoex <= 0:
            continue
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
        resultado.append({
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

    resultado.sort(key=lambda a: a['capital_estancado'], reverse=True)
    total = len(resultado)
    return {
        'fecha_corte': corte.isoformat(),
        'dias_historial': dias_historial,
        'dias_min': dias_min,
        'sucursal': sucursal,
        'resumen': {
            'capital_total': round(sum(a['capital_estancado'] for a in resultado), 2),
            'articulos': total,
            'sin_ventas': sum(a['sin_ventas'] for a in resultado),
            'promedio_dias': round(sum(a['dias_sin_vender'] for a in resultado) / total) if total else 0,
        },
        'articulos': resultado,
    }
