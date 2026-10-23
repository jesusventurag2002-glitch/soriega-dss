"""Agregados de ventas e inventario sobre SQLAlchemy (implementa puertos.demanda.RepositorioDemanda)."""
from sqlalchemy import func

from adaptadores.salida.modelos import Articulo, Inventario, Venta, db

# Solo las ventas comerciales son rotación de mercancía (las excepciones no).
ES_VENTA_COMERCIAL = Venta.excepcion.is_(None)


class RepositorioDemandaSQL:
    def articulos(self):
        return Articulo.query.all()

    def nombres(self):
        return dict(db.session.query(Articulo.codigo, Articulo.nombre).all())

    def unidades_vendidas(self):
        return db.session.query(Venta.articulo_codigo, func.sum(Venta.cantidad_neta)).filter(
            ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo).order_by(func.sum(Venta.cantidad_neta).desc()).all()

    def existencias(self):
        return db.session.query(
            Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal, func.sum(Inventario.existencia)
        ).group_by(Inventario.articulo_codigo, Inventario.origen_inventario, Inventario.sucursal).all()

    def ventas_por_sucursal(self):
        return db.session.query(
            Venta.articulo_codigo, Venta.sucursal, func.sum(Venta.cantidad_neta),
            func.min(Venta.fecha_emision), func.max(Venta.fecha_emision),
        ).filter(ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo, Venta.sucursal).all()

    def ventas_por_articulo(self):
        return db.session.query(
            Venta.articulo_codigo, func.sum(Venta.cantidad_neta),
            func.min(Venta.fecha_emision), func.max(Venta.fecha_emision),
        ).filter(ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo).all()

    def rango_ventas(self):
        return db.session.query(func.min(Venta.fecha_emision), func.max(Venta.fecha_emision)).one()

    def ultima_venta(self):
        return dict(db.session.query(Venta.articulo_codigo, func.max(Venta.fecha_emision)).filter(
            Venta.cantidad_neta > 0, ES_VENTA_COMERCIAL).group_by(Venta.articulo_codigo).all())
