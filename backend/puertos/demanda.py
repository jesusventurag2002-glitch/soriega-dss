"""Puerto de lectura de los agregados de ventas e inventario que usa el módulo de demanda."""
from datetime import date
from typing import Protocol


class RepositorioDemanda(Protocol):
    def articulos(self) -> list:
        """Catálogo (codigo, nombre, nombredegrupo, proveedor, costoex)."""

    def nombres(self) -> dict[str, str]: ...

    def unidades_vendidas(self) -> list[tuple]:
        """[(código, unidades netas)] de ventas comerciales."""

    def existencias(self) -> list[tuple]:
        """[(código, origen 'INV'|'INVAL', sucursal, total)]."""

    def ventas_por_sucursal(self) -> list[tuple]:
        """[(código, sucursal, unidades, primera fecha, última fecha)] de ventas comerciales."""

    def ventas_por_articulo(self) -> list[tuple]:
        """[(código, unidades, primera fecha, última fecha)] de ventas comerciales."""

    def rango_ventas(self) -> tuple[date | None, date | None]:
        """(primera, última) fecha de emisión de todo el historial."""

    def ultima_venta(self) -> dict[str, date]:
        """{código: última fecha con unidades vendidas} de ventas comerciales."""
