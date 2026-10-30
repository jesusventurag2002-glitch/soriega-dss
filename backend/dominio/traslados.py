"""Ciclo de vida de los documentos de traslado: estados, transiciones, cantidades por etapa e historial.

Un documento (TR-…) agrupa los artículos que van por una misma ruta (origen -> destino) y se aprueba, despacha y
recibe como una sola operación; cada artículo es una línea. Las funciones operan sobre cualquier objeto con los
atributos de `Documento` y `Linea` (los modelos ORM o, en las pruebas, objetos simples) y devuelven los eventos del
historial como diccionarios para que el caso de uso los guarde.
"""
from datetime import datetime
from typing import Protocol

from dominio.comun import entero, texto
from dominio.errores import Conflicto, ErrorDominio, NoEncontrado, Prohibido

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
ESTADOS_EXPORTABLES = ('aprobado', 'despachado', 'recibido', 'recibido_con_diferencias', 'cerrado')

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
ACCIONES_EN_LOTE = ['enviar', 'descartar']  # aprobar y rechazar exigen revisión individual
ORDEN_CLASE = {'A': 0, 'B': 1, 'C': 2}


class Linea(Protocol):
    """Se usa como clave de diccionario: debe ser hashable por identidad, como los modelos ORM."""

    id: int
    articulo_codigo: str
    articulo_nombre: str
    clasificacion_abc: str | None
    origen: str
    estado: str
    cantidad_sugerida: int
    cantidad_aprobada: int | None
    cantidad_despachada: int | None
    cantidad_recibida: int | None
    cobertura_dias: float | None
    retirado_en: datetime | None
    actualizado_en: datetime


class Documento(Protocol):
    id: int
    estado: str
    lineas: list[Linea]
    motivo_rechazo: str | None
    observaciones: str | None
    version: int
    actualizado_en: datetime


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


def prioridad_linea(t):
    """Clase ABC y luego la cobertura del destino (menos días = más urgente)."""
    return ORDEN_CLASE.get(t.clasificacion_abc, 3), t.cobertura_dias is None, t.cobertura_dias or 0, t.id


def acciones_disponibles(d, rol):
    return [a for a, (desde, roles) in TRANSICIONES.items() if d.estado in desde and (roles is None or rol in roles)]


def puede_retirar(d, rol):
    """En borrador cualquiera ajusta el documento; en aprobación solo el gerente puede quitar un artículo."""
    return d.estado == 'borrador' or (d.estado == 'pendiente_aprobacion' and rol == 'gerente')


def ref_articulo(t, antes=None, despues=None):
    """Artículo afectado por un evento del documento, con sus valores antes y después."""
    return {k: v for k, v in (('codigo', t.articulo_codigo), ('nombre', t.articulo_nombre), ('antes', antes),
                              ('despues', despues)) if v is not None}


def evento(d, tipo, usuario, estado_anterior=None, antes=None, despues=None, comentario=None, articulos=None):
    """Entrada del historial del documento; `usuario` es (nombre, rol)."""
    detalle = {k: v for k, v in (('antes', antes), ('despues', despues), ('comentario', comentario),
                                 ('articulos', articulos)) if v}
    return {'tipo': tipo, 'estado_anterior': estado_anterior, 'estado_nuevo': d.estado, 'usuario': usuario[0],
            'rol': usuario[1], 'fecha': datetime.now(), 'detalle': detalle or None}


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


def reservado(lineas_abiertas, excluir_id=None):
    """Unidades ya comprometidas en el origen por otras líneas abiertas del mismo artículo."""
    return sum(t.cantidad_aprobada if t.cantidad_aprobada is not None else t.cantidad_sugerida
               for t in lineas_abiertas if t.estado in ESTADOS_COMPROMETEN_ORIGEN and t.id != excluir_id)


def validar_disponible(nombre, origen, cantidad, existencia, reservadas):
    """No se puede reservar más de lo que hay en el origen descontando lo reservado por otros traslados."""
    disponible = existencia - reservadas
    if cantidad > disponible:
        raise ErrorDominio(
            f"{nombre}: {origen} tiene {max(disponible, 0)} unidades disponibles "
            f"(existencia {existencia}, {reservadas} reservadas en otros traslados). Ajusta la cantidad.")


def _validar_linea(l, cantidad, disponibilidad):
    validar_disponible(l.articulo_nombre, l.origen, cantidad, *disponibilidad(l))


def verificar_version(d, datos):
    version = datos.get('version')
    if version is None:
        raise ErrorDominio("Falta la versión del traslado.")
    if entero(version, 'La versión') != d.version:
        raise Conflicto(
            f"{folio(d)} cambió mientras lo revisabas (ahora está «{ESTADOS_TRASLADO[d.estado]}»). "
            "Se cargó la información actualizada; revisa antes de continuar.")


def cantidades_indicadas(d, datos, etiqueta, defecto=None, minimo=0):
    """Cantidad por artículo de {"cantidades": {"<id de línea>": n}}; si falta, se usa `defecto(línea)`."""
    indicadas = datos.get('cantidades') or {}
    if not isinstance(indicadas, dict):
        raise ErrorDominio("Las cantidades deben indicarse por artículo.")
    lineas = {str(l.id): l for l in lineas_vigentes(d)}
    ajenas = set(map(str, indicadas)) - set(lineas)
    if ajenas:
        raise ErrorDominio(f"{folio(d)} no contiene los artículos indicados ({', '.join(sorted(ajenas))}).")
    resultado = {}
    for clave, l in lineas.items():
        valor = indicadas.get(clave, indicadas.get(l.id))
        if valor in (None, ''):
            valor = defecto(l) if defecto else None
            if valor is None:
                raise ErrorDominio(f"Indica la {etiqueta.lower()} de {l.articulo_nombre}.")
        resultado[l] = entero(valor, f"{etiqueta} de {l.articulo_nombre}", minimo)
    return resultado


def cambios_de(cantidades, campo_antes, campo_despues):
    """Artículos cuya cantidad cambió respecto a la etapa anterior, para el historial."""
    return [ref_articulo(l, {campo_antes: getattr(l, campo_antes)}, {campo_despues: n})
            for l, n in cantidades.items() if n != getattr(l, campo_antes)]


def aplicar_accion(d, accion, datos, usuario, disponibilidad):
    """Ejecuta una transición sobre el documento completo validando estado, rol y cantidades de cada artículo.

    disponibilidad(línea) -> (existencia en el origen, unidades reservadas por otros traslados).
    Devuelve el evento del historial.
    """
    if accion not in TRANSICIONES:
        raise ErrorDominio(f"Acción desconocida: {accion}.")
    desde, roles = TRANSICIONES[accion]
    if d.estado not in desde:
        raise Conflicto(f"No se puede {VERBOS[accion]} {folio(d)} porque está «{ESTADOS_TRASLADO[d.estado]}».")
    if roles and usuario[1] not in roles:
        raise Prohibido(f"Solo un gerente puede {VERBOS[accion]} un traslado.")
    lineas = lineas_vigentes(d)
    if not lineas:
        raise ErrorDominio(f"{folio(d)} no tiene artículos.")

    anterior = d.estado
    comentario = texto(datos.get('comentario'))
    if accion == 'enviar':
        for l in lineas:
            _validar_linea(l, l.cantidad_sugerida, disponibilidad)
        fijar_estado(d, 'pendiente_aprobacion')
        e = evento(d, 'enviado_aprobacion', usuario, anterior, comentario=comentario)
    elif accion == 'descartar':
        d.motivo_rechazo = comentario or None
        fijar_estado(d, 'descartado')
        e = evento(d, 'descartado', usuario, anterior, comentario=comentario)
    elif accion == 'aprobar':
        cantidades = cantidades_indicadas(d, datos, 'La cantidad aprobada', lambda l: l.cantidad_sugerida, 1)
        for l, n in cantidades.items():
            _validar_linea(l, n, disponibilidad)
        cambios = cambios_de(cantidades, 'cantidad_sugerida', 'cantidad_aprobada')
        for l, n in cantidades.items():
            l.cantidad_aprobada = n
        fijar_estado(d, 'aprobado')
        e = evento(d, 'aprobado', usuario, anterior, despues={'unidades_aprobadas': sum(cantidades.values())},
                   comentario=comentario, articulos=cambios)
    elif accion == 'rechazar':
        motivo = texto(datos.get('motivo'))
        if len(motivo) < 3:
            raise ErrorDominio("Indica el motivo del rechazo.")
        d.motivo_rechazo = motivo
        fijar_estado(d, 'rechazado')
        e = evento(d, 'rechazado', usuario, anterior, comentario=motivo)
    elif accion == 'despachar':
        cantidades = cantidades_indicadas(d, datos, 'La cantidad despachada', lambda l: l.cantidad_aprobada, 0)
        for l, n in cantidades.items():
            if n > l.cantidad_aprobada:
                raise ErrorDominio(f"{l.articulo_nombre}: no se puede despachar más de lo aprobado ({l.cantidad_aprobada}).")
        if not sum(cantidades.values()):
            raise ErrorDominio("Indica al menos un artículo despachado.")
        cambios = cambios_de(cantidades, 'cantidad_aprobada', 'cantidad_despachada')
        for l, n in cantidades.items():
            l.cantidad_despachada = n
        fijar_estado(d, 'despachado')
        e = evento(d, 'despachado', usuario, anterior, despues={'unidades_despachadas': sum(cantidades.values())},
                   comentario=comentario, articulos=cambios)
    elif accion == 'recibir':
        cantidades = cantidades_indicadas(d, datos, 'La cantidad recibida')
        cambios = cambios_de(cantidades, 'cantidad_despachada', 'cantidad_recibida')
        if cambios and len(comentario) < 3:
            raise ErrorDominio("Lo recibido no coincide con lo despachado: describe la diferencia en las observaciones.")
        for l, n in cantidades.items():
            l.cantidad_recibida = n
        fijar_estado(d, 'recibido_con_diferencias' if cambios else 'recibido')
        for c in cambios:
            c['despues']['diferencia'] = c['despues']['cantidad_recibida'] - c['antes']['cantidad_despachada']
        e = evento(d, d.estado, usuario, anterior, despues={'unidades_recibidas': sum(cantidades.values())},
                   comentario=comentario, articulos=cambios)
    else:  # cerrar
        if d.estado == 'recibido_con_diferencias' and len(comentario) < 3:
            raise ErrorDominio("Para cerrar un traslado con diferencias, registra cómo se concilió.")
        fijar_estado(d, 'cerrado')
        e = evento(d, 'cerrado', usuario, anterior, comentario=comentario)
    tocar(d)
    return e


def editar(d, datos, usuario, disponibilidad):
    """{"lineas": [{"id": 8, "cantidad_sugerida": 20}], "observaciones": "..."}; devuelve los eventos (vacío = sin cambios).

    Las cantidades solo se ajustan en borrador.
    """
    eventos = []
    if datos.get('lineas'):
        if d.estado != 'borrador':
            raise Conflicto("Las cantidades solo se pueden editar mientras el traslado es un borrador.")
        vigentes = {l.id: l for l in lineas_vigentes(d)}
        modificados = []
        for item in datos['lineas']:
            l = vigentes.get(entero((item or {}).get('id'), 'El artículo', 1))
            if l is None:
                raise ErrorDominio(f"{folio(d)} no contiene ese artículo.")
            cantidad = entero(item.get('cantidad_sugerida'), f"La cantidad de {l.articulo_nombre}", 1)
            if cantidad != l.cantidad_sugerida:
                _validar_linea(l, cantidad, disponibilidad)
                modificados.append(ref_articulo(l, {'cantidad_sugerida': l.cantidad_sugerida}, {'cantidad_sugerida': cantidad}))
                l.cantidad_sugerida = cantidad
        if modificados:
            eventos.append(evento(d, 'cantidad_modificada', usuario, d.estado, comentario=texto(datos.get('comentario')),
                                  articulos=modificados))
    if 'observaciones' in datos:
        nuevas = texto(datos['observaciones']) or None
        if nuevas != d.observaciones:
            eventos.append(evento(d, 'observaciones', usuario, d.estado,
                                  antes={'observaciones': d.observaciones}, despues={'observaciones': nuevas}))
            d.observaciones = nuevas
    if eventos:
        tocar(d)
    return eventos


def retirar_linea(d, linea_id, datos, usuario):
    """Quita un artículo del documento sin afectar al resto; devuelve el evento."""
    if not puede_retirar(d, usuario[1]):
        raise Conflicto(f"No se pueden quitar artículos de {folio(d)} porque está «{ESTADOS_TRASLADO[d.estado]}».")
    vigentes = lineas_vigentes(d)
    l = next((x for x in vigentes if x.id == linea_id), None)
    if l is None:
        raise NoEncontrado(f"{folio(d)} no contiene ese artículo.")
    if len(vigentes) == 1:
        raise ErrorDominio("Es el único artículo del documento: descarta o rechaza el traslado completo.")
    l.retirado_en = datetime.now()
    l.estado = 'descartado'
    e = evento(d, 'articulo_retirado', usuario, d.estado, comentario=texto(datos.get('comentario')),
               articulos=[ref_articulo(l, {'cantidad_sugerida': l.cantidad_sugerida})])
    tocar(d)
    return e


def evento_alta(d, nuevo, lineas, usuario, comentario):
    """Evento de creación del documento o de artículos agregados a un borrador existente."""
    articulos = [ref_articulo(l, despues={'cantidad_sugerida': l.cantidad_sugerida}) for l in lineas]
    if nuevo:
        return evento(d, 'creado', usuario, despues={'articulos': len(lineas),
                                                     'unidades': sum(l.cantidad_sugerida for l in lineas)},
                      comentario=comentario, articulos=articulos)
    e = evento(d, 'articulos_agregados', usuario, d.estado, comentario=comentario, articulos=articulos)
    tocar(d)
    return e


def propuestas_por_destino(sugerencias, abiertas, clases):
    """Sugerencias de las clases elegidas agrupadas por sucursal, sin repetir artículos que ya tienen un traslado
    abierto en la misma ruta. Devuelve ({destino: [sugerencias]}, total de sugerencias de esas clases)."""
    ocupados = {(t.articulo_codigo, t.origen, t.destino) for t in abiertas}
    # El reparto del almacén entre sucursales es por artículo, así que filtrar por clase no altera las cantidades.
    elegidas = [s for s in sugerencias if s['clasificacion_abc'] in clases]
    por_destino = {}
    for s in elegidas:
        if (s['codigo'], ALMACEN, s['sucursal']) not in ocupados:
            por_destino.setdefault(s['sucursal'], []).append(s)
    return por_destino, len(elegidas)


def comprometido_en_almacen(abiertas):
    """{código: unidades del almacén reservadas en traslados abiertos}, que no se vuelven a repartir."""
    comprometido = {}
    for t in abiertas:
        if t.origen == ALMACEN and t.estado in ESTADOS_COMPROMETEN_ORIGEN:
            comprometido[t.articulo_codigo] = comprometido.get(t.articulo_codigo, 0) + (
                t.cantidad_aprobada if t.cantidad_aprobada is not None else t.cantidad_sugerida)
    return comprometido
