"""Caso de uso de la carga inicial de reportes (ventas, inventario de sucursal o almacén y tasas)."""
from datetime import datetime

from dominio import importacion as dom
from dominio.errores import ErrorDominio
from puertos.importacion import LectorReportes, RepositorioCargas


class CasosImportacion:
    def __init__(self, repo: RepositorioCargas, lector: LectorReportes):
        self.repo, self.lector = repo, lector

    def cargar(self, tipo_reporte, nombre_archivo, contenido, sucursal, usuario):
        """Procesa el archivo y deja registrada la importación (también si falla). Devuelve el mensaje para el usuario."""
        if tipo_reporte not in dom.TIPOS_REPORTE:
            raise ErrorDominio(f"tipo_reporte inválido. Opciones: {', '.join(sorted(dom.TIPOS_REPORTE))}.")
        if not nombre_archivo:
            raise ErrorDominio("No se recibió ningún archivo.")
        requiere_sucursal = tipo_reporte in dom.REQUIEREN_SUCURSAL
        sucursal = dom.canonizar_sucursal(sucursal, self.repo.sucursales_registradas()) if requiere_sucursal else None
        if requiere_sucursal and not sucursal:
            raise ErrorDominio("Indica la sucursal a la que pertenece el reporte.")

        def registrar(exito, mensaje, datos_hasta=None):
            self.repo.registrar_importacion(
                tipo_reporte=tipo_reporte, sucursal=sucursal, archivo=nombre_archivo[:255], exito=exito, mensaje=mensaje,
                fecha_importacion=datetime.now(), datos_hasta=datos_hasta, usuario=usuario[0])

        try:
            filas = self.lector.leer(nombre_archivo, contenido, tipo_reporte)
            mensaje, datos_hasta = self._procesar(tipo_reporte, filas, sucursal)
        except Exception as e:
            self.repo.revertir()
            registrar(False, str(e))
            raise
        registrar(True, mensaje, datos_hasta)
        return mensaje

    def _procesar(self, tipo_reporte, filas, sucursal):
        if tipo_reporte == 'ventas':
            ventas, tasas_bcv, conteos = dom.ventas_desde_filas(filas, sucursal)
            self.repo.reemplazar_ventas(sucursal, ventas)
            self.repo.registrar_tasas(tasas_bcv, 'tasa_bcv')
            self.repo.confirmar()
            return dom.mensaje_ventas(sucursal, ventas, tasas_bcv, conteos), self.repo.ultima_venta(sucursal)
        if tipo_reporte == 'tasas':
            tasas = dom.tasas_desde_filas(filas)
            self.repo.registrar_tasas(tasas, 'tasa_paralelo')
            self.repo.confirmar()
            desde, hasta = min(tasas), max(tasas)
            return (f"Tasas internas guardadas: {len(tasas)} días, del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}. "
                    f"Las ventas en USD se recalculan con estas tasas."), hasta
        origen = 'INV' if tipo_reporte == 'inv_fisico' else 'INVAL'
        self.repo.borrar_inventario(origen, sucursal)
        articulos, existencias, internos, conteos = dom.inventario_desde_filas(filas, origen, self.repo.grupos_catalogo())
        self.repo.guardar_inventario(origen, sucursal, articulos, existencias, internos)
        self.repo.confirmar()
        return dom.mensaje_inventario(origen, sucursal, conteos, internos), None
