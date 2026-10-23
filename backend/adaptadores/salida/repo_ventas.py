"""Ventas y tasas sobre SQLAlchemy (implementa puertos.ventas.RepositorioVentas)."""
from datetime import timedelta

from sqlalchemy import and_, case, func, or_, true

from adaptadores.salida.modelos import ConfigExcepcion, TasaInterna, Venta, db

# Facturación en USD como la hoja VENTA: Bs / tasa interna del día. Sin tasa interna para esa fecha
# (o si el archivo traía 'fact'), se usa el valor guardado al cargar.
VENTA_USD = case(
    (and_(Venta.factura_bs.isnot(None), TasaInterna.tasa_paralelo > 0), Venta.factura_bs / TasaInterna.tasa_paralelo),
    else_=Venta.factura_real_usd,
)
ANIO, MES = func.extract('year', Venta.fecha_emision), func.extract('month', Venta.fecha_emision)


def ventas_con_tasa(*columnas):
    return db.session.query(*columnas).select_from(Venta).outerjoin(TasaInterna, TasaInterna.fecha == Venta.fecha_emision)


def filtro_excepciones(excluir):
    return or_(Venta.excepcion.is_(None), Venta.excepcion.notin_(excluir)) if excluir else true()


def del_mes(mes, ano):
    return ANIO == ano, MES == mes


class RepositorioVentasSQL:
    def excepciones_guardadas(self):
        return {c.id: c.excluida for c in ConfigExcepcion.query}

    def guardar_excepciones(self, seleccion):
        if seleccion is None:
            ConfigExcepcion.query.delete()
        else:
            for id_, excluida in seleccion.items():
                config = db.session.get(ConfigExcepcion, id_) or ConfigExcepcion(id=id_)
                config.excluida = excluida
                db.session.add(config)
        db.session.commit()

    def fecha_corte(self):
        return db.session.query(func.max(Venta.fecha_emision)).scalar()

    def totales_mes(self, mes, ano, excluir):
        return ventas_con_tasa(func.coalesce(func.sum(VENTA_USD), 0), func.coalesce(func.sum(Venta.costo_real_usd), 0)
                               ).filter(*del_mes(mes, ano), filtro_excepciones(excluir)).one()

    def por_grupo_mes(self, mes, ano, excluir):
        return ventas_con_tasa(Venta.grupo_venta, func.sum(VENTA_USD)).filter(
            *del_mes(mes, ano), filtro_excepciones(excluir)).group_by(Venta.grupo_venta).order_by(func.sum(VENTA_USD).desc()).all()

    def meses_disponibles(self):
        return sorted({(int(a), int(m)) for a, m in db.session.query(ANIO, MES).distinct()}, reverse=True)

    def montos_excepcion(self, mes, ano):
        return dict(ventas_con_tasa(Venta.excepcion, func.sum(VENTA_USD)).filter(
            *del_mes(mes, ano), Venta.excepcion.isnot(None)).group_by(Venta.excepcion).all())

    def total_bruto(self, mes, ano):
        return ventas_con_tasa(func.coalesce(func.sum(VENTA_USD), 0)).filter(*del_mes(mes, ano)).scalar()

    def dias_sin_tasa(self, mes, ano):
        return ventas_con_tasa(func.count(func.distinct(Venta.fecha_emision))).filter(
            *del_mes(mes, ano), Venta.factura_bs.isnot(None),
            or_(TasaInterna.tasa_paralelo.is_(None), TasaInterna.tasa_paralelo <= 0)).scalar()

    def rentabilidad_mes(self, mes, ano, excluir):
        sucursal = func.coalesce(Venta.sucursal, 'Sin asignar').label('sucursal')
        sin_costo = or_(Venta.costo_real_usd.is_(None), Venta.costo_real_usd == 0)
        return ventas_con_tasa(
            sucursal, Venta.grupo_venta, func.sum(VENTA_USD), func.sum(func.coalesce(Venta.costo_real_usd, 0)),
            func.sum(case((sin_costo, VENTA_USD), else_=0)),
        ).filter(*del_mes(mes, ano), filtro_excepciones(excluir)).group_by(sucursal, Venta.grupo_venta).all()

    def diarios(self, desde, excluir):
        return dict(ventas_con_tasa(Venta.fecha_emision, func.sum(VENTA_USD)).filter(
            Venta.fecha_emision >= desde, filtro_excepciones(excluir)).group_by(Venta.fecha_emision).all())

    def tasa_vigente(self, fecha, campo):
        columna = getattr(TasaInterna, campo)
        t = TasaInterna.query.filter(TasaInterna.fecha <= fecha, columna.isnot(None)).order_by(TasaInterna.fecha.desc()).first()
        return (t.fecha, float(getattr(t, campo))) if t else None

    def historial_tasas(self, fecha, dias):
        return [(t.fecha, t.tasa_bcv, t.tasa_paralelo) for t in TasaInterna.query.filter(
            TasaInterna.fecha <= fecha, TasaInterna.fecha > fecha - timedelta(days=dias)).order_by(TasaInterna.fecha.desc())]

    def rango_tasas(self):
        return db.session.query(func.min(TasaInterna.fecha), func.max(TasaInterna.fecha)).one()

    def guardar_tasas_internas(self, tasas):
        for fecha, valor in tasas:
            existente = db.session.get(TasaInterna, fecha)
            if existente:
                existente.tasa_paralelo = valor
            else:
                db.session.add(TasaInterna(fecha=fecha, tasa_paralelo=valor))
        db.session.commit()

    def revertir(self):
        db.session.rollback()
