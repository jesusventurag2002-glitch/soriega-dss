import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from datetime import datetime
import re
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "clave_secreta_venezuela_crm"

# Conexión local a MySQL en XAMPP
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/sistema_inventario'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==================== MODELOS DE BASE DE DATOS ====================
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
    origen_inventario = db.Column(db.String(10)) # 'INV' o 'INVAL'
    existencia = db.Column(db.Integer, default=0)

class TasaInterna(db.Model):
    __tablename__ = 'tasas_internas'
    fecha = db.Column(db.Date, primary_key=True)
    tasa_paralelo = db.Column(db.Numeric(12, 4), nullable=False)

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


# ==================== RUTAS DE LA APLICACIÓN ====================

@app.route('/')
def index():
    hoy = datetime.today()
    año_actual = 2026  
    mes_actual = hoy.month

    mes_seleccionado = request.args.get('mes', default=mes_actual, type=int)
    año_seleccionado = request.args.get('ano', default=año_actual, type=int)

    meses_nombres = [
        {"numero": 1, "nombre": "Enero"}, {"numero": 2, "nombre": "Febrero"},
        {"numero": 3, "nombre": "Marzo"}, {"numero": 4, "nombre": "Abril"},
        {"numero": 5, "nombre": "Mayo"}, {"numero": 6, "nombre": "Junio"},
        {"numero": 7, "nombre": "Julio"}, {"numero": 8, "nombre": "Agosto"},
        {"numero": 9, "nombre": "Septiembre"}, {"numero": 10, "nombre": "Octubre"},
        {"numero": 11, "nombre": "Noviembre"}, {"numero": 12, "nombre": "Diciembre"}
    ]

    tasas = TasaInterna.query.order_by(TasaInterna.fecha.desc()).limit(5).all()
    
    ventas_filtradas = Venta.query.filter(
        func.extract('month', Venta.fecha_emision) == mes_seleccionado,
        func.extract('year', Venta.fecha_emision) == año_seleccionado
    ).all()

    total_factura_real = sum(float(v.factura_real_usd) for v in ventas_filtradas)
    total_costo_real = sum(float(v.costo_real_usd) for v in ventas_filtradas)
    total_utilidad_real = total_factura_real - total_costo_real

    ventas_por_grupo = db.session.query(
        Venta.grupo_venta,
        func.sum(Venta.factura_real_usd)
    ).filter(
        func.extract('month', Venta.fecha_emision) == mes_seleccionado,
        func.extract('year', Venta.fecha_emision) == año_seleccionado
    ).group_by(Venta.grupo_venta).order_by(func.sum(Venta.factura_real_usd).desc()).all()
     
    chart_labels = []
    chart_data = []
    for g in ventas_por_grupo:
        grupo_nombre = str(g[0]).strip().upper() if g[0] else "SIN GRUPO"
        chart_labels.append(grupo_nombre)
        chart_data.append(float(g[1]))

    return render_template('index.html', 
                           tasas=tasas, 
                           total_factura=round(total_factura_real, 2),
                           total_costo=round(total_costo_real, 2),
                           total_utilidad=round(total_utilidad_real, 2),
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           meses=meses_nombres,
                           mes_sel=mes_seleccionado,
                           ano_sel=año_seleccionado)

@app.route('/subir', methods=['POST'])
def subir_archivo():
    tipo_reporte = request.form.get('tipo_reporte')
    file = request.files.get('archivo')
    if not file: return redirect(url_for('index'))
    
    try:
        df = None
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            file.seek(0)
            df = pd.read_csv(file, header=1 if tipo_reporte == 'ventas' else 0)
        else:
            file.seek(0)
            df = pd.read_excel(file, header=1)

        if df is None or df.empty:
            raise Exception("Archivo vacío o no procesable.")

        df.columns = df.columns.str.strip().str.lower()
        
        if tipo_reporte == 'ventas':
            Venta.query.delete()
            db.session.commit()

            # EXCLUSIÓN DE CLIENTES ESPECIALES DE LA IMAGEN;
            CLIENTES_EXCLUIDOS = [
                "REPOSICION MARGARITA", 
                "REPOSICION VALENCIA", 
                "PLASTINET VALENCIA", 
                "SAUL NORIEGA",
                "MERCANCIA DANADA",
                "MERCANCIA EXTRAVIADA",
            ]

            for _, row in df.iterrows():
                codigo_art = str(row.get('codigo', row.get('cdg', ''))).split('.')[0].strip()
                if not codigo_art or codigo_art in ['nan', '']: continue
                
                # Regla de exclusión por cliente
                cliente_nombre = str(row.get('nombrecli', '')).strip().upper()
                if any(excluido in cliente_nombre for excluido in CLIENTES_EXCLUIDOS):
                    continue  

                grupo_venta = str(row.get('nombredegr', row.get('nombredegrupo', 'SIN GRUPO'))).strip().upper()
                if grupo_venta in ["", "NAN", "NONE", "0"]:
                    grupo_venta = "SIN GRUPO"

                fecha_raw = str(row.get('emision')).split()[0]
                try:
                    fecha_emision = datetime.strptime(fecha_raw, '%Y-%m-%d').date()
                except:
                    try: fecha_emision = datetime.strptime(fecha_raw, '%d/%m/%Y').date()
                    except: continue

                f_sistema = float(str(row.get('factor', 1.0)).replace(',', '.'))
                if f_sistema <= 0: f_sistema = 1.0
                precio_local = float(str(row.get('preciofin', 0)).replace(',', '.'))
                
                cant = int(float(str(row.get('cantidad', 0))))
                devueltos = int(float(str(row.get('cntdevuelt', 0))))
                cantidad_neta = cant - devueltos

                # CORRECCIÓN ENFOQUE: Uso de la columna exacta 'fact' del Excel
                if 'fact' in df.columns:
                    factura_real = float(str(row.get('fact', 0)).replace(',', '.'))
                else:
                    # Fallback matemático exacto a la fórmula del Excel si no viniera calculado
                    factura_real = ((precio_local * 1.16) * cantidad_neta) / f_sistema

                if 'costo' in df.columns:
                    costo_real = float(str(row.get('costo', 0)).replace(',', '.'))
                else:
                    costo_ex_excel = float(str(row.get('costoex', 0)).replace(',', '.'))
                    costo_real = costo_ex_excel * cantidad_neta
                
                utilidad_real = factura_real - costo_real
                
                nueva_venta = Venta(
                    documento=str(row.get('documento')), articulo_codigo=codigo_art, 
                    nombre_articulo=str(row.get('nombre', 'Artículo')), grupo_venta=grupo_venta,
                    cantidad_neta=cantidad_neta, precio_fin_moneda_local=precio_local, 
                    factor_sistema=f_sistema, factura_real_usd=factura_real, 
                    costo_real_usd=costo_real, utilidad_real_usd=utilidad_real,
                    fecha_emision=fecha_emision
                )
                db.session.add(nueva_venta)
            db.session.commit()
            flash("Historial de ventas indexado con éxito basándose en la facturación real ('fact').", "success")
            
        elif tipo_reporte in ['inv_fisico', 'inv_inval']:
            origen = 'INV' if tipo_reporte == 'inv_fisico' else 'INVAL'
            for _, row in df.iterrows():
                codigo_art = str(row.get('codigo', row.get('cdg', row.get('codigoart', '')))).split('.')[0].strip()
                if not codigo_art or codigo_art in ['nan', '']: continue
                
                try: existencia_actual = int(float(str(row.get('existencia', 0)).replace(',', '.')))
                except: existencia_actual = 0
                try: costo_val = float(str(row.get('costoex', row.get('costo', 0))).replace(',', '.'))
                except: costo_val = 0.0

                grupo_val = str(row.get('nombredegr', row.get('nombredegrupo', 'SIN GRUPO'))).strip().upper()

                art = Articulo.query.get(codigo_art)
                if not art:
                    art = Articulo(codigo=codigo_art, nombre=str(row.get('nombre', row.get('nombreart', 'Sin Nombre'))).strip(), nombredegrupo=grupo_val, costoex=costo_val)
                    db.session.add(art)
                else:
                    art.costoex = costo_val
                    if grupo_val and grupo_val != "NAN": art.nombredegrupo = grupo_val
                
                inv = Inventario.query.filter_by(articulo_codigo=codigo_art, origen_inventario=origen).first()
                if inv: inv.existencia = existencia_actual
                else: db.session.add(Inventario(articulo_codigo=codigo_art, origen_inventario=origen, existencia=existencia_actual))
            db.session.commit()
            flash(f"Consolidado del inventario {origen} guardado exitosamente.", "success")
            
    except Exception as e:
        db.session.rollback()
        flash(f"Error procesando la matriz: {str(e)}", "danger")
    return redirect(url_for('index'))

@app.route('/logistica', methods=['POST'])
def logistica():
    tipo_analisis = request.form.get('tipo_analisis')
    dias = int(request.form.get('dias', 15))
    articulos = Articulo.query.all()
    resultados = []
    
    for art in articulos:
        stock_inv = sum(i.existencia for i in Inventario.query.filter_by(articulo_codigo=art.codigo, origen_inventario='INV').all())
        stock_inval = sum(i.existencia for i in Inventario.query.filter_by(articulo_codigo=art.codigo, origen_inventario='INVAL').all())
        
        ventas_art = Venta.query.filter_by(articulo_codigo=art.codigo).all()
        total_unidades = sum(v.cantidad_neta for v in ventas_art)
        
        fechas = [v.fecha_emision for v in ventas_art]
        rango_dias = (max(fechas) - min(fechas)).days + 1 if fechas else 30
        vpd = total_unidades / (rango_dias if rango_dias > 0 else 1)
        demanda_proyectada = vpd * dias
        
        if tipo_analisis == 'traslado':
            if stock_inv < demanda_proyectada and stock_inval > 0:
                faltante = demanda_proyectada - stock_inv
                cant_a_mover = min(round(faltante), stock_inval)
                if cant_a_mover > 0:
                    resultados.append({
                        'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                        'origen': 'INVAL', 'destino': 'INV', 'cantidad': cant_a_mover, 'disponible_almacen': stock_inval
                    })
                    
        elif tipo_analisis == 'reposicion':
            stock_total = stock_inv + stock_inval
            if stock_total < demanda_proyectada:
                cant_a_pedir = max(0, round(demanda_proyectada - stock_total))
                if cant_a_pedir > 0:
                    resultados.append({
                        'codigo': art.codigo, 'nombre': art.nombre, 'grupo': art.nombredegrupo,
                        'proveedor': art.proveedor, 'cantidad_pedir': cant_a_pedir, 'deficit': round(demanda_proyectada - stock_total)
                    })

    return render_template('logistica.html', resultados=resultados, tipo_analisis=tipo_analisis, dias=dias)

@app.route('/guardar_tasa', methods=['POST'])
def guardar_tasa():
    lista_tasas_raw = request.form.get('lista_tasas')
    if lista_tasas_raw and lista_tasas_raw.strip():
        lineas = lista_tasas_raw.strip().split('\n')
        for linea in lineas:
            linea = linea.strip()
            if not linea: continue
            partes = re.split(r'[\t,\s]+', linea)
            if len(partes) >= 2:
                fecha_str, tasa_str = partes[0], partes[1]
                try:
                    if '-' in fecha_str: fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                    elif '/' in fecha_str: fecha_obj = datetime.strptime(fecha_str, '%d/%m/%Y').date()
                    else: continue
                    tasa_val = float(tasa_str.replace(',', '.'))
                    tasa_existente = TasaInterna.query.get(fecha_obj)
                    if tasa_existente: tasa_existente.tasa_paralelo = tasa_val
                    else: db.session.add(TasaInterna(fecha=fecha_obj, tasa_paralelo=tasa_val))
                except: continue
        db.session.commit()
        flash("Historial cambiario actualizado.", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)