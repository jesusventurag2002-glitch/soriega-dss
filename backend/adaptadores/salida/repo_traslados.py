"""Repositorio de traslados sobre SQLAlchemy (implementa puertos.traslados.RepositorioTraslados)."""
import json
import re

from sqlalchemy import and_, case, func, or_

from adaptadores.salida.modelos import DocumentoTraslado, EventoDocumento, Traslado, db
from dominio.comun import texto
from dominio.traslados import ESTADOS_ABIERTOS, ESTADOS_TRASLADO

# Agregados de los artículos vigentes de cada documento, para ordenar la bandeja.
LINEAS_DEL_DOCUMENTO = and_(Traslado.documento_id == DocumentoTraslado.id, Traslado.retirado_en.is_(None))
ORDEN_ABC = case((Traslado.clasificacion_abc == 'A', 0), (Traslado.clasificacion_abc == 'B', 1),
                 (Traslado.clasificacion_abc == 'C', 2), else_=3)


def agregado_lineas(expresion):
    return db.select(expresion).where(LINEAS_DEL_DOCUMENTO).correlate(DocumentoTraslado).scalar_subquery()


MEJOR_ABC = agregado_lineas(func.min(ORDEN_ABC))
MENOR_COBERTURA = agregado_lineas(func.coalesce(func.min(Traslado.cobertura_dias), 1e9))
TOTAL_UNIDADES = agregado_lineas(func.sum(func.coalesce(
    Traslado.cantidad_recibida, Traslado.cantidad_despachada, Traslado.cantidad_aprobada, Traslado.cantidad_sugerida)))
ORDEN_ESTADO = case(*[(DocumentoTraslado.estado == e, i) for i, e in enumerate(ESTADOS_TRASLADO)], else_=99)
ORDENES = {
    # Prioridad: el artículo de mayor clase ABC y luego la cobertura más baja del destino.
    'prioridad': [MEJOR_ABC, MENOR_COBERTURA, DocumentoTraslado.id],
    'estado': [ORDEN_ESTADO, MEJOR_ABC, DocumentoTraslado.id],
    'cantidad': [TOTAL_UNIDADES.desc(), DocumentoTraslado.id],
    'reciente': [DocumentoTraslado.actualizado_en.desc(), DocumentoTraslado.id.desc()],
    'ruta': [DocumentoTraslado.destino, DocumentoTraslado.origen, DocumentoTraslado.id],
}


def con_lineas(*condiciones):
    return DocumentoTraslado.lineas.any(and_(Traslado.retirado_en.is_(None), *condiciones))


def filtrar_documentos(args):
    q = DocumentoTraslado.query
    for campo in ('origen', 'destino', 'tipo'):
        if args.get(campo):
            q = q.filter(getattr(DocumentoTraslado, campo) == args[campo])
    if args.get('abc'):
        q = q.filter(con_lineas(Traslado.clasificacion_abc == args['abc'].upper()))
    if args.get('sucursal'):
        q = q.filter(or_(DocumentoTraslado.origen == args['sucursal'], DocumentoTraslado.destino == args['sucursal']))
    termino = texto(args.get('q')).lower()
    if termino:
        condiciones = [con_lineas(or_(func.lower(Traslado.articulo_nombre).like(f'%{termino}%'),
                                      func.lower(Traslado.articulo_codigo).like(f'%{termino}%')))]
        coincidencia_folio = re.fullmatch(r'(?:tr-?)?0*(\d+)', termino)
        if coincidencia_folio:
            condiciones.append(DocumentoTraslado.id == int(coincidencia_folio.group(1)))
        q = q.filter(or_(*condiciones))
    return q


class RepositorioTrasladosSQL:
    def obtener(self, id_):
        return db.session.get(DocumentoTraslado, id_)

    def borrador_de_ruta(self, tipo, origen, destino):
        return DocumentoTraslado.query.filter_by(tipo=tipo, origen=origen, destino=destino, estado='borrador').first()

    def nuevo_documento(self, **campos):
        d = DocumentoTraslado(**campos)
        db.session.add(d)
        db.session.flush()
        return d

    def agregar_lineas(self, d, filas):
        lineas = [Traslado(**f) for f in filas]
        d.lineas.extend(lineas)
        db.session.flush()
        return lineas

    def agregar_evento(self, d, evento):
        detalle = evento['detalle']
        db.session.add(EventoDocumento(
            documento_id=d.id, **{k: v for k, v in evento.items() if k != 'detalle'},
            detalle=json.dumps(detalle, ensure_ascii=False) if detalle else None,
        ))

    def eventos(self, d):
        return EventoDocumento.query.filter_by(documento_id=d.id).order_by(EventoDocumento.fecha, EventoDocumento.id).all()

    def lineas_abiertas(self, origen=None, destino=None, articulo=None, tipo=None, articulos=None):
        q = Traslado.query.filter(Traslado.estado.in_(ESTADOS_ABIERTOS))
        for columna, valor in ((Traslado.origen, origen), (Traslado.destino, destino), (Traslado.articulo_codigo, articulo),
                               (Traslado.tipo, tipo)):
            if valor is not None:
                q = q.filter(columna == valor)
        if articulos is not None:
            q = q.filter(Traslado.articulo_codigo.in_(articulos))
        return q.all()

    def conteo_por_estado(self, filtros):
        return dict(filtrar_documentos(filtros).with_entities(DocumentoTraslado.estado, func.count())
                    .group_by(DocumentoTraslado.estado).all())

    def _en_estados(self, filtros, estados):
        return filtrar_documentos(filtros).filter(DocumentoTraslado.estado.in_(estados))

    def contar(self, filtros, estados):
        return self._en_estados(filtros, estados).count()

    def pagina(self, filtros, estados, orden, desde, cantidad):
        return (self._en_estados(filtros, estados).order_by(*ORDENES.get(orden, ORDENES['prioridad']))
                .offset(desde).limit(cantidad).all())

    def rutas(self):
        return (sorted(o for (o,) in db.session.query(DocumentoTraslado.origen).distinct()),
                sorted(d for (d,) in db.session.query(DocumentoTraslado.destino).distinct()))

    def confirmar(self):
        db.session.commit()

    def revertir(self):
        db.session.rollback()
