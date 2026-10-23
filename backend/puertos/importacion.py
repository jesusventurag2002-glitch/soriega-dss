"""Puertos de la carga de reportes: el lector de archivos y el repositorio donde se vuelcan."""
from datetime import date
from typing import Protocol


class LectorReportes(Protocol):
    def leer(self, nombre_archivo: str, contenido: bytes, tipo_reporte: str) -> list[dict]:
        """Filas del reporte con los encabezados en minúsculas y None en las celdas vacías.

        Lanza ErrorDominio si el formato no se soporta, faltan las columnas del tipo de reporte o no hay filas.
        """


class RepositorioCargas(Protocol):
    def sucursales_registradas(self) -> set[str]: ...

    def reemplazar_ventas(self, sucursal: str, ventas: list[dict]) -> None:
        """Las ventas de esa sucursal (y las de cargas antiguas sin sucursal) se sustituyen por estas."""

    def ultima_venta(self, sucursal: str) -> date | None: ...

    def registrar_tasas(self, por_fecha: dict, campo: str) -> None:
        """Inserta o actualiza 'tasa_paralelo' o 'tasa_bcv' por fecha."""

    def borrar_inventario(self, origen: str, sucursal: str | None) -> None: ...

    def grupos_catalogo(self) -> dict[str, str]:
        """{código: grupo} de los artículos registrados."""

    def guardar_inventario(self, origen: str, sucursal: str | None, articulos: dict, existencias: dict,
                           internos: set) -> None:
        """Crea o actualiza los artículos, agrega las existencias y elimina los artículos de uso interno."""

    def registrar_importacion(self, **campos) -> None:
        """Guarda el registro de la carga (exitosa o no) de forma definitiva."""

    def confirmar(self) -> None: ...

    def revertir(self) -> None: ...
