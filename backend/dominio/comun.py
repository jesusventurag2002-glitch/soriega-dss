"""Normalización de valores recibidos (JSON o reportes), común a todos los módulos."""
from datetime import datetime

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


def numero(valor, defecto=0.0):
    try:
        n = float(str(valor).replace(',', '.'))
    except (TypeError, ValueError):
        return defecto
    return defecto if n != n else n


def parsear_fecha(valor):
    """date desde datetime/Timestamp o texto 'AAAA-MM-DD' / 'DD/MM/AAAA' (con hora opcional); None si no se reconoce."""
    if valor is None or valor != valor:  # NaN / NaT
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
