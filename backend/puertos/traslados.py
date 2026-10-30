"""Puertos que necesita el módulo de traslados."""
from typing import Protocol

from dominio.traslados import Documento, Linea


class RepositorioTraslados(Protocol):
    def obtener(self, id_: int) -> Documento | None: ...

    def borrador_de_ruta(self, tipo: str, origen: str, destino: str) -> Documento | None: ...

    def nuevo_documento(self, **campos) -> Documento:
        """Crea el documento y le asigna id."""

    def agregar_lineas(self, d: Documento, filas: list[dict]) -> list[Linea]: ...

    def agregar_evento(self, d: Documento, evento: dict) -> None: ...

    def eventos(self, d: Documento) -> list:
        """Historial del documento en orden cronológico."""

    def lineas_abiertas(self, origen: str | None = None, destino: str | None = None, articulo: str | None = None,
                        tipo: str | None = None, articulos: list[str] | None = None) -> list[Linea]: ...

    def conteo_por_estado(self, filtros: dict) -> dict[str, int]: ...

    def contar(self, filtros: dict, estados: list[str]) -> int: ...

    def pagina(self, filtros: dict, estados: list[str], orden: str, desde: int, cantidad: int) -> list[Documento]: ...

    def rutas(self) -> tuple[list[str], list[str]]:
        """(orígenes, destinos) usados en algún documento."""

    def confirmar(self) -> None: ...

    def revertir(self) -> None: ...


class ConsultaInventario(Protocol):
    def stock_en(self, ubicacion: str, codigo: str) -> int: ...

    def articulo(self, codigo: str):
        """Artículo del catálogo (codigo, nombre, …) o None."""

    def sucursales_con_inventario(self) -> list[str]: ...

    def costos(self, codigos: list[str]) -> dict[str, float]:
        """Costo sin IVA (costoex) por código."""

    def tasa_interna(self, hasta) -> float | None:
        """Tasa interna vigente a esa fecha (la última registrada)."""
