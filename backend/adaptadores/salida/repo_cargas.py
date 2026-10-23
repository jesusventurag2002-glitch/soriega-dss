"""Volcado de reportes cargados sobre SQLAlchemy (implementa puertos.importacion.RepositorioCargas)."""
from sqlalchemy import func, or_

from adaptadores.salida.modelos import Articulo, Importacion, Inventario, TasaInterna, Venta, db


class RepositorioCargasSQL:
    def sucursales_registradas(self):
        existentes = {s for (s,) in db.session.query(Venta.sucursal).distinct() if s}
        return existentes | {s for (s,) in db.session.query(Inventario.sucursal).distinct() if s}

    def reemplazar_ventas(self, sucursal, ventas):
        # Sin commit intermedio: si algo falla, el rollback conserva las ventas previas.
        Venta.query.filter(or_(Venta.sucursal == sucursal, Venta.sucursal.is_(None))).delete(synchronize_session=False)
        db.session.add_all(Venta(**v) for v in ventas)

    def ultima_venta(self, sucursal):
        return db.session.query(func.max(Venta.fecha_emision)).filter(Venta.sucursal == sucursal).scalar()

    def registrar_tasas(self, por_fecha, campo):
        if not por_fecha:
            return
        existentes = {t.fecha: t for t in TasaInterna.query.filter(TasaInterna.fecha.in_(list(por_fecha)))}
        for fecha, valor in por_fecha.items():
            tasa = existentes.get(fecha)
            if tasa is None:
                tasa = TasaInterna(fecha=fecha)
                db.session.add(tasa)
            setattr(tasa, campo, valor)

    def borrar_inventario(self, origen, sucursal):
        # En sucursales también se reemplaza el de cargas antiguas sin sucursal.
        anterior = Inventario.query.filter(Inventario.origen_inventario == origen)
        if origen == 'INV':
            anterior = anterior.filter(or_(Inventario.sucursal == sucursal, Inventario.sucursal.is_(None)))
        anterior.delete(synchronize_session=False)

    def grupos_catalogo(self):
        return dict(db.session.query(Articulo.codigo, Articulo.nombredegrupo).all())

    def guardar_inventario(self, origen, sucursal, articulos, existencias, internos):
        actuales = {a.codigo: a for a in Articulo.query.all()}  # una consulta, no una por fila
        for codigo, a in articulos.items():
            if a['nuevo']:
                db.session.add(Articulo(codigo=codigo, nombre=a['nombre'], nombredegrupo=a['grupo'], costoex=a['costo']))
            else:
                actuales[codigo].costoex = a['costo']
                if a['grupo']:
                    actuales[codigo].nombredegrupo = a['grupo']
        db.session.add_all(
            Inventario(articulo_codigo=c, origen_inventario=origen, existencia=e, sucursal=sucursal, precio_usd=p)
            for c, (e, p) in existencias.items()
        )
        if internos:
            Inventario.query.filter(Inventario.articulo_codigo.in_(internos)).delete(synchronize_session=False)
            Articulo.query.filter(Articulo.codigo.in_(internos)).delete(synchronize_session=False)

    def registrar_importacion(self, **campos):
        db.session.add(Importacion(**campos))
        db.session.commit()

    def confirmar(self):
        db.session.commit()

    def revertir(self):
        db.session.rollback()
