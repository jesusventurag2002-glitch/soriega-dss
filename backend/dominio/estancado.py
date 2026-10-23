"""Seguimiento de decisiones sobre mercancía estancada (promoción o devolución a proveedor)."""
from datetime import datetime

from dominio.comun import texto
from dominio.errores import Conflicto, ErrorDominio
from dominio.traslados import cantidad_vigente, folio

TIPOS_ACCION_ESTANCADO = {'promocion': 'Descuento / promoción', 'devolucion_proveedor': 'Devolución a proveedor'}


def validar_nueva_accion(articulo, tipo, hay_pendiente):
    """hay_pendiente(código, tipo) -> bool: solo puede haber una acción pendiente de cada tipo por artículo."""
    if articulo is None:
        raise ErrorDominio("El artículo no existe.")
    if tipo not in TIPOS_ACCION_ESTANCADO:
        raise ErrorDominio("Tipo de acción inválido.")
    if hay_pendiente(articulo.codigo, tipo):
        raise Conflicto(f"Ya hay una acción «{TIPOS_ACCION_ESTANCADO[tipo]}» pendiente para este artículo.")


def cerrar_accion(accion, datos, usuario):
    """{"estado": "completada" | "descartada", "resultado": "..."}; solo desde pendiente."""
    if accion.estado != 'pendiente':
        raise Conflicto("La acción ya fue cerrada.")
    estado, resultado = datos.get('estado'), texto(datos.get('resultado'))
    if estado not in ('completada', 'descartada'):
        raise ErrorDominio("Estado inválido.")
    if estado == 'completada' and len(resultado) < 3:
        raise ErrorDominio("Describe el resultado obtenido.")
    accion.estado, accion.resultado = estado, resultado or None
    accion.cerrado_por, accion.cerrado_en = usuario[0], datetime.now()


def retornos_por_articulo(lineas):
    """Retornos al almacén en curso de cada artículo, para el seguimiento del capital estancado."""
    retornos = {}
    for t in lineas:
        retornos.setdefault(t.articulo_codigo, []).append(
            {'id': t.documento_id, 'folio': folio(t.documento), 'origen': t.origen, 'estado': t.estado,
             'cantidad': cantidad_vigente(t)})
    return retornos
