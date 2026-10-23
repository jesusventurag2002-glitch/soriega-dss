"""Errores de negocio. El adaptador de entrada decide el código HTTP según la clase."""


class ErrorDominio(Exception):
    """Datos inválidos o regla incumplida."""


class Prohibido(ErrorDominio):
    """El rol del usuario no permite la operación."""


class NoEncontrado(ErrorDominio):
    pass


class Conflicto(ErrorDominio):
    """El estado actual del registro no permite la operación (o cambió mientras se revisaba)."""
