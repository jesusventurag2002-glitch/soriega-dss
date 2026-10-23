"""Casos de uso de demanda: sugerencias de traslado y compra, productos críticos y capital estancado."""
from dominio import demanda as dom
from dominio.traslados import ALMACEN
from puertos.demanda import RepositorioDemanda
from puertos.traslados import RepositorioTraslados


class CasosDemanda:
    def __init__(self, repo: RepositorioDemanda, traslados: RepositorioTraslados):
        self.repo, self.traslados = repo, traslados

    def clasificacion_abc(self):
        return dom.clasificar_abc(self.repo.unidades_vendidas())

    def _demanda(self):
        return dom.demanda(self.repo.existencias(), self.repo.ventas_por_sucursal(), self.repo.ventas_por_articulo())

    def sugerencias_traslado(self, dias, comprometido_almacen=None):
        return dom.sugerencias_traslado(self.repo.articulos(), self._demanda(), self.clasificacion_abc(), dias,
                                        comprometido_almacen)

    def reposicion(self, dias):
        return dom.reposicion(self.repo.articulos(), self._demanda(), self.clasificacion_abc(), dias)

    def productos_criticos(self, sucursal=None, dias=dom.DIAS_COBERTURA_CRITICA):
        return dom.productos_criticos(self._demanda(), self.clasificacion_abc(), self.repo.nombres(),
                                      self.traslados.lineas_abiertas(origen=ALMACEN), sucursal, dias)

    def capital_estancado(self, dias_min, sucursal=None):
        return dom.capital_estancado(*self.repo.rango_ventas(), self.repo.ultima_venta(), self.repo.existencias(),
                                     self.repo.articulos(), dias_min, sucursal)
