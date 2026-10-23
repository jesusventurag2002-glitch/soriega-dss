"""Normalización de valores recibidos (JSON o reportes), común a todos los módulos."""
from dominio.errores import ErrorDominio


def texto(valor, defecto=''):
    if valor is None or valor != valor:  # valor != valor: NaN
        return defecto
    return str(valor).strip() or defecto


def entero(valor, campo, minimo=0):
    if isinstance(valor, bool) or (isinstance(valor, float) and not valor.is_integer()):
        raise ErrorDominio(f"{campo} debe ser un número entero.")
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ErrorDominio(f"{campo} debe ser un número entero.")
    if n < minimo:
        raise ErrorDominio(f"{campo} debe ser mayor o igual a {minimo}.")
    return n
