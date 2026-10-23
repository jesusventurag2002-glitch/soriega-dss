"""Puerto de ventas y tasas. Los montos en USD ya vienen convertidos con la tasa interna del día."""
from datetime import date
from typing import Protocol


class RepositorioVentas(Protocol):
    def excepciones_guardadas(self) -> dict[str, bool]: ...

    def guardar_excepciones(self, seleccion: dict[str, bool] | None) -> None:
        """None restablece los valores por defecto."""

    def fecha_corte(self) -> date | None:
        """Última fecha de emisión registrada."""

    def totales_mes(self, mes: int, ano: int, excluir: list[str]) -> tuple[float, float]:
        """(facturación, costo) del mes sin las excepciones indicadas."""

    def por_grupo_mes(self, mes: int, ano: int, excluir: list[str]) -> list[tuple]:
        """[(grupo, total)] de mayor a menor."""

    def meses_disponibles(self) -> list[tuple[int, int]]:
        """[(año, mes)] con ventas, del más reciente al más antiguo."""

    def montos_excepcion(self, mes: int, ano: int) -> dict[str, float]: ...

    def total_bruto(self, mes: int, ano: int) -> float: ...

    def dias_sin_tasa(self, mes: int, ano: int) -> int:
        """Días del mes con ventas en Bs sin tasa interna cargada (su USD se calculó con FACTOR)."""

    def rentabilidad_mes(self, mes: int, ano: int, excluir: list[str]) -> list[tuple]:
        """[(sucursal, grupo, total, costo, ventas sin costo)]."""

    def diarios(self, desde: date, excluir: list[str]) -> dict[date, float]: ...

    def tasa_vigente(self, fecha: date, campo: str) -> tuple[date, float] | None:
        """Última tasa ('tasa_bcv' o 'tasa_paralelo') registrada en o antes de la fecha."""

    def historial_tasas(self, fecha: date, dias: int) -> list[tuple]:
        """[(fecha, bcv, interna)] de los `dias` hasta `fecha`, del más reciente al más antiguo."""

    def rango_tasas(self) -> tuple[date | None, date | None]: ...

    def guardar_tasas_internas(self, tasas: list[tuple[date, float]]) -> None: ...

    def revertir(self) -> None: ...
