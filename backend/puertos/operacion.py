"""Puertos de la operación diaria: seguimiento de estancado, piso de venta y tablero del centro de decisiones."""
from datetime import date
from typing import Protocol


class RepositorioAcciones(Protocol):
    """Acciones sobre mercancía estancada (articulo_codigo, tipo, estado, capital_al_registrar, …)."""

    def listar(self, estado: str | None, tipo: str | None, limite: int) -> list:
        """Las más recientes primero."""

    def de_articulos(self, codigos: list[str]) -> list:
        """Todas las acciones de esos artículos, las más recientes primero."""

    def pendientes(self) -> list:
        """Pendientes, de la más antigua a la más reciente."""

    def hay_pendiente(self, codigo: str, tipo: str) -> bool: ...

    def obtener(self, id_: int): ...

    def agregar(self, **campos): ...

    def confirmar(self) -> None: ...


class RepositorioTienda(Protocol):
    def buscar_articulos(self, termino: str, limite: int) -> list:
        """Por código o nombre; primero la coincidencia exacta de código y luego por nombre."""

    def existencias(self, codigos: list[str]) -> list[tuple]:
        """[(código, origen 'INV'|'INVAL', sucursal, total, precio USD)]."""

    def ubicaciones_con_discrepancia(self, codigos: list[str]) -> set[tuple[str, str]]:
        """{(código, ubicación)} con una discrepancia pendiente."""

    def listar_discrepancias(self, estado: str | None, sucursal: str | None, limite: int) -> list: ...

    def hay_discrepancia_pendiente(self, codigo: str, sucursal: str) -> bool: ...

    def obtener_discrepancia(self, id_: int): ...

    def agregar_discrepancia(self, **campos): ...

    def confirmar(self) -> None: ...


class RepositorioTablero(Protocol):
    def documentos_por_estado(self, sucursal: str | None) -> dict[str, int]: ...

    def documentos(self, sucursal: str | None, estados: list[str], orden: str, limite: int) -> list:
        """orden: 'prioridad' (clase ABC y cobertura) o 'antiguos' (sin actualizar desde hace más tiempo)."""

    def actividad(self, sucursal: str | None, limite: int) -> list[tuple]:
        """[(evento, documento)] de los traslados, del más reciente al más antiguo."""

    def discrepancias_pendientes(self, sucursal: str | None) -> int: ...

    def importaciones(self, limite: int) -> list:
        """Las más recientes primero."""

    def ultima_importacion(self, tipo: str, sucursal: str | None = None):
        """Última importación exitosa de ese tipo (y sucursal, si se indica), o None."""

    def ventas_hasta(self) -> dict[str | None, date]:
        """{sucursal: última emisión}; la clave None son ventas de cargas antiguas sin sucursal."""

    def tasas_hasta(self) -> date | None: ...

    def almacen_cargado(self) -> bool: ...
