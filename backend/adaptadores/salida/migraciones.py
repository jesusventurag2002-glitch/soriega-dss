"""Ajustes de esquema que create_all no hace (columnas nuevas en tablas existentes) y migración de datos."""
import json

from sqlalchemy import inspect, text

from adaptadores.salida.modelos import DocumentoTraslado, EventoDocumento, EventoTraslado, Traslado, db
from dominio.traslados import ESTADOS_ABIERTOS, ref_articulo


COLUMNAS_AGREGADAS = [
    ('ventas', 'sucursal', 'VARCHAR(100)'),
    ('inventarios', 'sucursal', 'VARCHAR(100)'),
    ('ventas', 'factura_bs', 'NUMERIC(16,4)'),
    ('ventas', 'excepcion', 'VARCHAR(50)'),
    ('tasas_internas', 'tasa_bcv', 'NUMERIC(12,4)'),
    ('traslados', 'documento_id', 'INTEGER REFERENCES traslado_documentos(id)'),
    ('traslados', 'retirado_en', 'TIMESTAMP'),
    ('inventarios', 'precio_usd', 'NUMERIC(12,4)'),
]


def migrar_esquema():
    """create_all no agrega columnas a tablas existentes: se añaden aquí las incorporadas después."""
    inspector = inspect(db.engine)
    for tabla, columna, tipo in COLUMNAS_AGREGADAS:
        if columna not in {c['name'] for c in inspector.get_columns(tabla)}:
            with db.engine.begin() as conexion:
                conexion.execute(text(f'ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}'))
    # tasa_paralelo era obligatoria; ahora una fecha puede tener solo tasa BCV.
    if db.engine.dialect.name == 'postgresql':
        with db.engine.begin() as conexion:
            conexion.execute(text('ALTER TABLE tasas_internas ALTER COLUMN tasa_paralelo DROP NOT NULL'))
    agrupar_traslados_en_documentos()


def agrupar_traslados_en_documentos():
    """Traslados creados antes de los documentos (uno por artículo): se agrupan en documentos TR por ruta.

    Los abiertos se agrupan por ruta y estado para poder seguir operándolos juntos; los finalizados, además, por
    día de creación para no mezclar operaciones históricas distintas. Su historial se copia al documento.
    """
    sueltos = Traslado.query.filter(Traslado.documento_id.is_(None)).order_by(Traslado.id).all()
    if not sueltos:
        return
    grupos = {}
    for t in sueltos:
        clave = (t.tipo, t.origen, t.destino, t.estado)
        if t.estado not in ESTADOS_ABIERTOS:
            clave += (t.creado_en.date(),)
        grupos.setdefault(clave, []).append(t)
    for lineas in grupos.values():
        primera = lineas[0]
        unicos = lambda campo: '; '.join(dict.fromkeys(getattr(l, campo) for l in lineas if getattr(l, campo))) or None
        d = DocumentoTraslado(
            tipo=primera.tipo, origen=primera.origen, destino=primera.destino, estado=primera.estado,
            horizonte_dias=primera.horizonte_dias, motivo_rechazo=unicos('motivo_rechazo'),
            observaciones=unicos('observaciones'), creado_por=primera.creado_por,
            creado_en=min(l.creado_en for l in lineas), actualizado_en=max(l.actualizado_en for l in lineas),
        )
        db.session.add(d)
        d.lineas.extend(lineas)
        db.session.flush()
        por_id = {l.id: l for l in lineas}
        for e in EventoTraslado.query.filter(EventoTraslado.traslado_id.in_(por_id)).order_by(EventoTraslado.fecha, EventoTraslado.id):
            detalle = json.loads(e.detalle) if e.detalle else {}
            detalle['articulos'] = [ref_articulo(por_id[e.traslado_id])]
            db.session.add(EventoDocumento(documento_id=d.id, tipo=e.tipo, estado_anterior=e.estado_anterior,
                                           estado_nuevo=e.estado_nuevo, usuario=e.usuario, rol=e.rol, fecha=e.fecha,
                                           detalle=json.dumps(detalle, ensure_ascii=False)))
    db.session.commit()
