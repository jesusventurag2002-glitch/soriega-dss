"""Modelos SQLAlchemy: el esquema de la base de datos (adaptador de salida)."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Articulo(db.Model):
    __tablename__ = 'articulos'
    codigo = db.Column(db.String(50), primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    referencia = db.Column(db.String(100))
    marca = db.Column(db.String(100))
    nombredegrupo = db.Column(db.String(100), default="Sin Grupo")
    costoex = db.Column(db.Numeric(12, 4), default=0.0000)
    proveedor = db.Column(db.String(150), default="Proveedor General")

class Inventario(db.Model):
    __tablename__ = 'inventarios'
    id = db.Column(db.Integer, primary_key=True)
    articulo_codigo = db.Column(db.String(50))
    origen_inventario = db.Column(db.String(10)) # 'INV' (sucursales) o 'INVAL' (almacén principal)
    existencia = db.Column(db.Integer, default=0)
    sucursal = db.Column(db.String(100))  # solo para 'INV'; el almacén principal no tiene sucursal
    precio_usd = db.Column(db.Numeric(12, 4))  # precio de venta en USD sin IVA en esa ubicación

class TasaInterna(db.Model):
    __tablename__ = 'tasas_internas'
    fecha = db.Column(db.Date, primary_key=True)
    tasa_paralelo = db.Column(db.Numeric(12, 4))  # tasa interna del día (hoja TASA / sistema)
    tasa_bcv = db.Column(db.Numeric(12, 4))  # tasa BCV del día (FACTOR del reporte de ventas)

class ConfigExcepcion(db.Model):
    """Excepciones elegidas en "Administrar excepciones"; sin fila, rige el valor por defecto de EXCEPCIONES."""
    __tablename__ = 'config_excepciones'
    id = db.Column(db.String(50), primary_key=True)
    excluida = db.Column(db.Boolean, nullable=False)

class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(50), nullable=False)
    articulo_codigo = db.Column(db.String(50))
    nombre_articulo = db.Column(db.String(255))
    grupo_venta = db.Column(db.String(100), default="Sin Grupo")
    cantidad_neta = db.Column(db.Integer, nullable=False)
    precio_fin_moneda_local = db.Column(db.Numeric(12, 4), nullable=False)
    factor_sistema = db.Column(db.Numeric(12, 4), nullable=False)
    factura_real_usd = db.Column(db.Numeric(12, 4), default=0.0000)
    costo_real_usd = db.Column(db.Numeric(12, 4), default=0.0000)
    utilidad_real_usd = db.Column(db.Numeric(12, 4), default=0.0000)
    fecha_emision = db.Column(db.Date, nullable=False)
    sucursal = db.Column(db.String(100))  # indicada al cargar el reporte; el archivo no la trae
    factura_bs = db.Column(db.Numeric(16, 4))  # PRECIOFIN * 1.16 * cantidad neta; el USD se calcula con la tasa interna
    excepcion = db.Column(db.String(50))  # id de EXCEPCIONES si no es facturación comercial

class DocumentoTraslado(db.Model):
    """Documento de traslado (TR-…): agrupa los artículos de una misma ruta y lleva el ciclo de vida completo."""
    __tablename__ = 'traslado_documentos'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default='reposicion')  # 'reposicion' (almacén -> sucursal) o 'retorno'
    origen = db.Column(db.String(100), nullable=False, index=True)
    destino = db.Column(db.String(100), nullable=False, index=True)
    estado = db.Column(db.String(30), nullable=False, default='borrador', index=True)
    horizonte_dias = db.Column(db.Integer)
    motivo_rechazo = db.Column(db.Text)
    observaciones = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    actualizado_en = db.Column(db.DateTime, nullable=False)
    # Se incrementa en cada cambio: una acción enviada con una versión vieja (doble clic, otra pestaña) se rechaza.
    version = db.Column(db.Integer, nullable=False, default=1)
    lineas = db.relationship('Traslado', backref='documento', order_by='Traslado.id', lazy='selectin')

class EventoDocumento(db.Model):
    """Historial inmutable de cada documento: quién hizo qué, cuándo y con qué valores antes y después."""
    __tablename__ = 'traslado_documento_eventos'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('traslado_documentos.id'), nullable=False, index=True)
    tipo = db.Column(db.String(40), nullable=False)
    estado_anterior = db.Column(db.String(30))
    estado_nuevo = db.Column(db.String(30))
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(30))
    fecha = db.Column(db.DateTime, nullable=False, index=True)
    detalle = db.Column(db.Text)  # JSON: {"antes": {...}, "despues": {...}, "comentario": "...", "articulos": [...]}

class Traslado(db.Model):
    """Línea de un documento de traslado: un artículo con sus cantidades en cada etapa del ciclo.

    Su estado replica el del documento (las consultas de stock comprometido y de traslados abiertos lo usan);
    una línea retirada de un borrador queda 'descartado' con retirado_en.
    """
    __tablename__ = 'traslados'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('traslado_documentos.id'), index=True)
    retirado_en = db.Column(db.DateTime)
    articulo_codigo = db.Column(db.String(50), nullable=False, index=True)
    articulo_nombre = db.Column(db.String(255), nullable=False)
    clasificacion_abc = db.Column(db.String(1))
    tipo = db.Column(db.String(20), nullable=False, default='reposicion')  # 'reposicion' (almacén -> sucursal) o 'retorno'
    origen = db.Column(db.String(100), nullable=False)  # ALMACEN o nombre de sucursal
    destino = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(30), nullable=False, default='borrador', index=True)
    cantidad_sugerida = db.Column(db.Integer, nullable=False)
    cantidad_aprobada = db.Column(db.Integer)
    cantidad_despachada = db.Column(db.Integer)
    cantidad_recibida = db.Column(db.Integer)
    # Foto del momento en que se generó la propuesta (las existencias vienen de exportaciones).
    stock_origen = db.Column(db.Integer)
    stock_destino = db.Column(db.Integer)
    cobertura_dias = db.Column(db.Float)  # días que cubría el stock del destino; menor = más urgente
    horizonte_dias = db.Column(db.Integer)
    motivo_rechazo = db.Column(db.Text)
    observaciones = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    actualizado_en = db.Column(db.DateTime, nullable=False)
    # Se incrementa en cada cambio: una acción enviada con una versión vieja (doble clic, otra pestaña) se rechaza.
    version = db.Column(db.Integer, nullable=False, default=1)

class EventoTraslado(db.Model):
    """Historial por artículo anterior a los documentos de traslado; se conserva y se copia al documento al migrar."""
    __tablename__ = 'traslado_eventos'
    id = db.Column(db.Integer, primary_key=True)
    traslado_id = db.Column(db.Integer, db.ForeignKey('traslados.id'), nullable=False, index=True)
    tipo = db.Column(db.String(40), nullable=False)
    estado_anterior = db.Column(db.String(30))
    estado_nuevo = db.Column(db.String(30))
    usuario = db.Column(db.String(100))
    rol = db.Column(db.String(30))
    fecha = db.Column(db.DateTime, nullable=False, index=True)
    detalle = db.Column(db.Text)  # JSON: {"antes": {...}, "despues": {...}, "comentario": "..."}

class Discrepancia(db.Model):
    """Alerta del piso de venta: lo contado físicamente en la tienda no coincide con el inventario del sistema."""
    __tablename__ = 'discrepancias'
    id = db.Column(db.Integer, primary_key=True)
    articulo_codigo = db.Column(db.String(50), nullable=False, index=True)
    articulo_nombre = db.Column(db.String(255), nullable=False)
    sucursal = db.Column(db.String(100), nullable=False, index=True)
    existencia_sistema = db.Column(db.Integer, nullable=False)  # foto del inventario cargado al reportar
    existencia_contada = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    estado = db.Column(db.String(20), nullable=False, default='pendiente', index=True)  # pendiente | revisada
    resolucion = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    revisado_por = db.Column(db.String(100))
    revisado_en = db.Column(db.DateTime)

class AccionEstancado(db.Model):
    """Seguimiento de decisiones sobre mercancía estancada (promoción o devolución a proveedor)."""
    __tablename__ = 'acciones_estancado'
    id = db.Column(db.Integer, primary_key=True)
    articulo_codigo = db.Column(db.String(50), nullable=False, index=True)
    articulo_nombre = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # 'promocion' | 'devolucion_proveedor'
    estado = db.Column(db.String(20), nullable=False, default='pendiente')  # pendiente | completada | descartada
    capital_al_registrar = db.Column(db.Numeric(14, 2))
    comentario = db.Column(db.Text)
    resultado = db.Column(db.Text)
    creado_por = db.Column(db.String(100))
    creado_en = db.Column(db.DateTime, nullable=False)
    cerrado_por = db.Column(db.String(100))
    cerrado_en = db.Column(db.DateTime)

class Importacion(db.Model):
    """Registro de cada archivo cargado, para saber de cuándo son los datos que se muestran."""
    __tablename__ = 'importaciones'
    id = db.Column(db.Integer, primary_key=True)
    tipo_reporte = db.Column(db.String(20), nullable=False)
    sucursal = db.Column(db.String(100))
    archivo = db.Column(db.String(255))
    exito = db.Column(db.Boolean, nullable=False)
    mensaje = db.Column(db.Text)
    fecha_importacion = db.Column(db.DateTime, nullable=False)
    datos_hasta = db.Column(db.Date)  # última fecha contenida en el archivo, cuando la trae (ventas, tasas)
    usuario = db.Column(db.String(100))
