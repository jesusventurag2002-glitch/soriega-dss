"""Consultas de inventario y catálogo sobre SQLAlchemy (implementa puertos.traslados.ConsultaInventario)."""
from sqlalchemy import func

from adaptadores.salida.modelos import Articulo, Inventario, TasaInterna, db
from dominio.traslados import ALMACEN


class InventarioSQL:
    def stock_en(self, ubicacion, codigo):
        q = db.session.query(func.coalesce(func.sum(Inventario.existencia), 0)).filter(Inventario.articulo_codigo == codigo)
        if ubicacion == ALMACEN:
            q = q.filter(Inventario.origen_inventario == 'INVAL')
        else:
            q = q.filter(Inventario.origen_inventario == 'INV', Inventario.sucursal == ubicacion)
        return int(q.scalar() or 0)

    def articulo(self, codigo):
        return db.session.get(Articulo, codigo)

    def sucursales_con_inventario(self):
        return sorted(s for (s,) in db.session.query(Inventario.sucursal).filter(
            Inventario.origen_inventario == 'INV').distinct() if s)

    def costos(self, codigos):
        return {a.codigo: float(a.costoex or 0) for a in Articulo.query.filter(Articulo.codigo.in_(codigos))}

    def tasa_interna(self, hasta):
        t = TasaInterna.query.filter(TasaInterna.fecha <= hasta, TasaInterna.tasa_paralelo.isnot(None))             .order_by(TasaInterna.fecha.desc()).first()
        return float(t.tasa_paralelo) if t else None
