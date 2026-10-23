"""Repositorios SQLAlchemy de la operación diaria (implementan puertos.operacion)."""
from sqlalchemy import func, or_

from adaptadores.salida.modelos import (
    AccionEstancado, Articulo, Discrepancia, DocumentoTraslado, EventoDocumento, Importacion, Inventario, TasaInterna, Venta,
    db,
)
from adaptadores.salida.repo_traslados import ORDENES


class RepositorioAccionesSQL:
    def listar(self, estado, tipo, limite):
        q = AccionEstancado.query
        for columna, valor in ((AccionEstancado.estado, estado), (AccionEstancado.tipo, tipo)):
            if valor:
                q = q.filter(columna == valor)
        return q.order_by(AccionEstancado.creado_en.desc()).limit(limite).all()

    def de_articulos(self, codigos):
        return AccionEstancado.query.filter(AccionEstancado.articulo_codigo.in_(codigos)).order_by(
            AccionEstancado.creado_en.desc()).all()

    def pendientes(self):
        return AccionEstancado.query.filter_by(estado='pendiente').order_by(AccionEstancado.creado_en).all()

    def hay_pendiente(self, codigo, tipo):
        return AccionEstancado.query.filter_by(articulo_codigo=codigo, tipo=tipo, estado='pendiente').first() is not None

    def obtener(self, id_):
        return db.session.get(AccionEstancado, id_)

    def agregar(self, **campos):
        accion = AccionEstancado(**campos)
        db.session.add(accion)
        return accion

    def confirmar(self):
        db.session.commit()


class RepositorioTiendaSQL:
    def buscar_articulos(self, termino, limite):
        patron = f'%{termino.lower()}%'
        return Articulo.query.filter(or_(
            func.lower(Articulo.codigo).like(patron), func.lower(Articulo.nombre).like(patron),
        )).order_by((Articulo.codigo == termino).desc(), Articulo.nombre).limit(limite).all()

    def existencias(self, codigos):
        return db.session.query(
            Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia),
            func.max(Inventario.precio_usd),
        ).filter(Inventario.articulo_codigo.in_(codigos)).group_by(
            Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal).all()

    def ubicaciones_con_discrepancia(self, codigos):
        return {(d.articulo_codigo, d.sucursal) for d in Discrepancia.query.filter(
            Discrepancia.articulo_codigo.in_(codigos), Discrepancia.estado == 'pendiente')}

    def listar_discrepancias(self, estado, sucursal, limite):
        q = Discrepancia.query
        for columna, valor in ((Discrepancia.estado, estado), (Discrepancia.sucursal, sucursal)):
            if valor:
                q = q.filter(columna == valor)
        return q.order_by(Discrepancia.creado_en.desc()).limit(limite).all()

    def hay_discrepancia_pendiente(self, codigo, sucursal):
        return Discrepancia.query.filter_by(articulo_codigo=codigo, sucursal=sucursal, estado='pendiente').first() is not None

    def obtener_discrepancia(self, id_):
        return db.session.get(Discrepancia, id_)

    def agregar_discrepancia(self, **campos):
        d = Discrepancia(**campos)
        db.session.add(d)
        return d

    def confirmar(self):
        db.session.commit()


def de_la_sucursal(q, sucursal):
    return q.filter(or_(DocumentoTraslado.origen == sucursal, DocumentoTraslado.destino == sucursal)) if sucursal else q


class RepositorioTableroSQL:
    ORDENES = {'prioridad': ORDENES['prioridad'], 'antiguos': [DocumentoTraslado.actualizado_en]}

    def documentos_por_estado(self, sucursal):
        return dict(de_la_sucursal(DocumentoTraslado.query, sucursal).with_entities(
            DocumentoTraslado.estado, func.count()).group_by(DocumentoTraslado.estado).all())

    def documentos(self, sucursal, estados, orden, limite):
        return de_la_sucursal(DocumentoTraslado.query, sucursal).filter(DocumentoTraslado.estado.in_(estados)).order_by(
            *self.ORDENES[orden]).limit(limite).all()

    def actividad(self, sucursal, limite):
        q = db.session.query(EventoDocumento, DocumentoTraslado).join(
            DocumentoTraslado, DocumentoTraslado.id == EventoDocumento.documento_id)
        return de_la_sucursal(q, sucursal).order_by(EventoDocumento.fecha.desc(), EventoDocumento.id.desc()).limit(limite).all()

    def discrepancias_pendientes(self, sucursal):
        q = Discrepancia.query.filter_by(estado='pendiente')
        return (q.filter_by(sucursal=sucursal) if sucursal else q).count()

    def importaciones(self, limite):
        return Importacion.query.order_by(Importacion.fecha_importacion.desc()).limit(limite).all()

    def ultima_importacion(self, tipo, sucursal=None):
        q = Importacion.query.filter_by(tipo_reporte=tipo, exito=True)
        if sucursal is not None:
            q = q.filter_by(sucursal=sucursal)
        return q.order_by(Importacion.fecha_importacion.desc()).first()

    def ventas_hasta(self):
        return dict(db.session.query(Venta.sucursal, func.max(Venta.fecha_emision)).group_by(Venta.sucursal).all())

    def tasas_hasta(self):
        return db.session.query(func.max(TasaInterna.fecha)).filter(TasaInterna.tasa_paralelo.isnot(None)).scalar()

    def almacen_cargado(self):
        return Inventario.query.filter_by(origen_inventario='INVAL').first() is not None
