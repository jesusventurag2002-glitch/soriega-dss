"""Lectura de reportes .xlsx/.xls/.csv con pandas (implementa puertos.importacion.LectorReportes)."""
import io

import pandas as pd

from dominio.errores import ErrorDominio

# Al menos una columna de cada grupo debe existir en el archivo.
COLUMNAS_REQUERIDAS = {
    'ventas': [('codigo', 'cdg'), ('emision',)],
    'inventario': [('codigo', 'cdg', 'codigoart'), ('existencia',)],
    'tasas': [('fecha',), ('tasa',)],
}
MAX_FILAS_TITULO = 5  # filas de título que puede traer el reporte antes de los encabezados


def normalizar_columnas(columnas):
    return pd.Index(columnas).astype(str).str.strip().str.lower()


class LectorPandas:
    def leer(self, nombre_archivo, contenido, tipo_reporte):
        nombre = nombre_archivo.lower()
        contenido = io.BytesIO(contenido)

        if nombre.endswith('.csv'):
            def leer(**kwargs):
                contenido.seek(0)
                try:
                    return pd.read_csv(contenido, **kwargs)
                except UnicodeDecodeError:
                    contenido.seek(0)
                    return pd.read_csv(contenido, encoding='latin-1', **kwargs)
        elif nombre.endswith(('.xlsx', '.xls')):
            # El sistema administrativo exporta .XLS que en realidad son .xlsx;
            # pandas detecta el formato real por el contenido, no por la extensión.
            libro = pd.ExcelFile(contenido)
            # Las tasas pueden venir en el libro de pedidos completo: se usa su hoja TASA.
            hoja = next((h for h in libro.sheet_names if h.strip().upper() == 'TASA'), 0) if tipo_reporte == 'tasas' else 0

            def leer(**kwargs):
                return libro.parse(sheet_name=hoja, **kwargs)
        else:
            raise ErrorDominio("Formato no soportado. Usa .xlsx, .xls o .csv.")

        # Los reportes traen un título antes de los encabezados ("Lista De Inventario...",
        # "Artículos Vendidos..."), así que se busca la fila que contiene las columnas requeridas.
        requeridas = COLUMNAS_REQUERIDAS[tipo_reporte if tipo_reporte in COLUMNAS_REQUERIDAS else 'inventario']
        for header in range(MAX_FILAS_TITULO + 1):
            columnas = normalizar_columnas(leer(header=header, nrows=0).columns)
            if all(any(c in columnas for c in grupo) for grupo in requeridas):
                break
        else:
            faltantes = ', '.join(' / '.join(g) for g in requeridas)
            raise ErrorDominio(
                f"No se encontraron las columnas requeridas ({faltantes}) en las primeras "
                f"{MAX_FILAS_TITULO + 1} filas. Verifica que el archivo corresponda al tipo de reporte seleccionado."
            )

        df = leer(header=header)
        if df.empty:
            raise ErrorDominio("Archivo vacío o no procesable.")
        df.columns = normalizar_columnas(df.columns)
        # Celdas vacías como None: el dominio no depende de cómo pandas representa los faltantes (NaN, NaT, NA).
        return df.astype(object).where(df.notna(), None).to_dict('records')
