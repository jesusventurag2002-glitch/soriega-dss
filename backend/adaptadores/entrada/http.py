"""Utilidades HTTP compartidas por los blueprints."""
from urllib.parse import unquote

from flask import request

from dominio.errores import Conflicto, NoEncontrado, Prohibido

ESTADOS_HTTP = {Prohibido: 403, NoEncontrado: 404, Conflicto: 409}


def estado_http(error):
    return next((s for clase, s in ESTADOS_HTTP.items() if isinstance(error, clase)), 400)


def usuario_actual():
    """Responsable de la acción según el login simulado del frontend (cabeceras X-Usuario / X-Rol, codificadas).

    No es autenticación: identifica a quien opera mientras no exista un inicio de sesión real.
    """
    nombre = unquote(request.headers.get('X-Usuario', '')).strip()[:100] or 'Sin identificar'
    rol = unquote(request.headers.get('X-Rol', '')).strip().lower()[:30]
    return nombre, rol
