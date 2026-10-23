"""Casos de uso de la operación diaria: seguimiento de estancado, piso de venta y centro de decisiones."""
from datetime import datetime

from aplicacion.demanda import CasosDemanda
from dominio import estancado, tienda
from dominio.comun import entero, numero, texto
from dominio.demanda import DIAS_COBERTURA_CRITICA
from dominio.errores import Conflicto, ErrorDominio, NoEncontrado
from puertos.operacion import RepositorioAcciones, RepositorioTablero, RepositorioTienda
from puertos.traslados import ConsultaInventario, RepositorioTraslados


class CasosEstancado:
    def __init__(self, acciones: RepositorioAcciones, demanda: CasosDemanda, traslados: RepositorioTraslados,
                 inventario: ConsultaInventario):
        self.acciones, self.demanda, self.traslados, self.inventario = acciones, demanda, traslados, inventario

    def capital_estancado(self, dias_min, limite, sucursal):
        """Capital estancado con el seguimiento de cada artículo: acciones registradas y retornos al almacén en curso."""
        datos = self.demanda.capital_estancado(dias_min, sucursal)
        if datos is None:
            raise ErrorDominio("No hay historial de ventas cargado.")
        articulos = datos['articulos'][:limite]
        codigos = [a['codigo'] for a in articulos]
        acciones = {}
        for accion in self.acciones.de_articulos(codigos):
            acciones.setdefault(accion.articulo_codigo, []).append(accion)
        retornos = estancado.retornos_por_articulo(self.traslados.lineas_abiertas(tipo='retorno', articulos=codigos))
        for a in articulos:
            a['acciones'] = acciones.get(a['codigo'], [])
            a['retornos'] = retornos.get(a['codigo'], [])
        return {**datos, 'articulos': articulos, 'sucursales': self.inventario.sucursales_con_inventario()}

    def listar(self, estado, tipo):
        return self.acciones.listar(estado, tipo, 200)

    def registrar(self, datos, usuario):
        """{"articulo_codigo", "tipo": "promocion" | "devolucion_proveedor", "comentario", "capital"}"""
        codigo, tipo = texto(datos.get('articulo_codigo')), datos.get('tipo')
        art = self.inventario.articulo(codigo) if codigo else None
        estancado.validar_nueva_accion(art, tipo, self.acciones.hay_pendiente)
        accion = self.acciones.agregar(
            articulo_codigo=codigo, articulo_nombre=art.nombre, tipo=tipo, estado='pendiente',
            capital_al_registrar=numero(datos.get('capital'), None), comentario=texto(datos.get('comentario')) or None,
            creado_por=usuario[0], creado_en=datetime.now(),
        )
        self.acciones.confirmar()
        return accion

    def obtener(self, id_):
        accion = self.acciones.obtener(id_)
        if accion is None:
            raise NoEncontrado("La acción no existe.")
        return accion

    def cerrar(self, accion, datos, usuario):
        estancado.cerrar_accion(accion, datos, usuario)
        self.acciones.confirmar()
        return accion


class CasosTienda:
    def __init__(self, repo: RepositorioTienda, inventario: ConsultaInventario, demanda: CasosDemanda):
        self.repo, self.inventario, self.demanda = repo, inventario, demanda

    def consultar_stock(self, termino):
        """Existencias de artículos concretos por código o nombre, para consultar desde la tienda.

        Devuelve [(artículo, clase ABC, [(ubicación, existencia, precio USD, discrepancia pendiente)])].
        """
        termino = texto(termino)
        if len(termino) < 2:
            raise ErrorDominio("Escribe al menos 2 caracteres del código o el nombre.")
        articulos = self.repo.buscar_articulos(termino, 20)
        codigos = [a.codigo for a in articulos]
        existencias = tienda.existencias_por_ubicacion(self.repo.existencias(codigos))
        abc = self.demanda.clasificacion_abc()
        pendientes = self.repo.ubicaciones_con_discrepancia(codigos)
        return [(a, abc.get(a.codigo), [(u, n, p, (a.codigo, u) in pendientes) for u, n, p in existencias.get(a.codigo, [])])
                for a in articulos]

    def listar_discrepancias(self, estado, sucursal):
        return self.repo.listar_discrepancias(estado, sucursal, 200)

    def reportar_discrepancia(self, datos, usuario):
        """{"articulo_codigo", "sucursal", "existencia_contada", "comentario"}; la existencia del sistema sale del inventario."""
        codigo, sucursal = texto(datos.get('articulo_codigo')), texto(datos.get('sucursal'))
        art = self.inventario.articulo(codigo) if codigo else None
        if art is None:
            raise ErrorDominio("El artículo no existe.")
        if not sucursal:
            raise ErrorDominio("Indica la ubicación donde se contó la mercancía.")
        contada = entero(datos.get('existencia_contada'), 'La cantidad contada', 0)
        sistema = self.inventario.stock_en(sucursal, codigo)
        comentario = texto(datos.get('comentario'))
        tienda.validar_conteo(contada, sistema, comentario)
        if self.repo.hay_discrepancia_pendiente(codigo, sucursal):
            raise Conflicto("Ya hay una discrepancia pendiente de revisión para este artículo en esa ubicación.")
        d = self.repo.agregar_discrepancia(
            articulo_codigo=codigo, articulo_nombre=art.nombre, sucursal=sucursal, existencia_sistema=sistema,
            existencia_contada=contada, comentario=comentario, estado='pendiente', creado_por=usuario[0],
            creado_en=datetime.now())
        self.repo.confirmar()
        return d

    def obtener_discrepancia(self, id_):
        d = self.repo.obtener_discrepancia(id_)
        if d is None:
            raise NoEncontrado("La discrepancia no existe.")
        return d

    def revisar_discrepancia(self, d, datos, usuario):
        tienda.revisar_discrepancia(d, datos, usuario)
        self.repo.confirmar()
        return d


class CasosTablero:
    def __init__(self, repo: RepositorioTablero, demanda: CasosDemanda, acciones: RepositorioAcciones,
                 inventario: ConsultaInventario):
        self.repo, self.demanda, self.acciones, self.inventario = repo, demanda, acciones, inventario

    def importaciones(self, limite=50):
        return self.repo.importaciones(limite)

    def estado_de_los_datos(self):
        """Qué datos hay cargados por ubicación, cuándo se importaron y hasta qué fecha llegan."""
        def ultima(tipo, sucursal=None):
            i = self.repo.ultima_importacion(tipo, sucursal)
            return {'importado_en': i.fecha_importacion.isoformat(timespec='seconds') if i else None,
                    'datos_hasta': i.datos_hasta.isoformat() if i and i.datos_hasta else None}

        con_inventario = set(self.inventario.sucursales_con_inventario())
        ventas_hasta = self.repo.ventas_hasta()
        tasas_hasta = self.repo.tasas_hasta()
        return {
            'sucursales': [{
                'sucursal': s,
                'inventario': {'cargado': s in con_inventario, **ultima('inv_fisico', s)},
                # La fecha de los datos de ventas se toma de las propias ventas (última emisión), no de la importación.
                'ventas': {'cargado': s in ventas_hasta, **ultima('ventas', s),
                           'datos_hasta': ventas_hasta[s].isoformat() if s in ventas_hasta else None},
            } for s in sorted(con_inventario | {s for s in ventas_hasta if s})],
            'almacen': {'cargado': self.repo.almacen_cargado(), **ultima('inv_inval')},
            'tasas': {**ultima('tasas'), 'datos_hasta': tasas_hasta.isoformat() if tasas_hasta else None},
            'ventas_sin_sucursal': None in ventas_hasta,
        }

    def tablero(self, sucursal):
        """Indicadores, pendientes y actividad del centro de decisiones; con sucursal, la vista individual.

        Los documentos, eventos, acciones e importaciones se devuelven como entidades para que la entrada los serialice.
        """
        por_estado = self.repo.documentos_por_estado(sucursal)
        criticos = self.demanda.productos_criticos(sucursal)
        capital = self.demanda.capital_estancado(90, sucursal)
        acciones = self.acciones.pendientes()
        return {
            'sucursal': sucursal,
            'generado_en': datetime.now().isoformat(timespec='seconds'),
            'traslados': {
                'borradores': por_estado.get('borrador', 0),
                'por_aprobar': por_estado.get('pendiente_aprobacion', 0),
                'por_despachar': por_estado.get('aprobado', 0),
                'en_transito': por_estado.get('despachado', 0),
                'con_diferencias': por_estado.get('recibido_con_diferencias', 0),
                'por_cerrar': por_estado.get('recibido', 0) + por_estado.get('recibido_con_diferencias', 0),
            },
            'pendientes': {
                'por_aprobar': self.repo.documentos(sucursal, ['pendiente_aprobacion'], 'prioridad', 5),
                'en_transito': self.repo.documentos(sucursal, ['despachado'], 'antiguos', 5),
                'con_diferencias': self.repo.documentos(sucursal, ['recibido_con_diferencias'], 'antiguos', 5),
            },
            'criticos': {'total': len(criticos), 'dias_cobertura': DIAS_COBERTURA_CRITICA, 'items': criticos[:5]},
            'capital_estancado': None if capital is None else {
                'total': capital['resumen']['capital_total'], 'articulos': capital['resumen']['articulos'],
                'dias_min': capital['dias_min'], 'fecha_corte': capital['fecha_corte'],
                'consolidado': sucursal is None,
            },
            'acciones_estancado': {'pendientes': len(acciones), 'items': acciones[:5]},
            'discrepancias_pendientes': self.repo.discrepancias_pendientes(sucursal),
            'actividad': self.repo.actividad(sucursal, 10),
            'importaciones': self.repo.importaciones(5),
            'datos': self.estado_de_los_datos(),
        }
