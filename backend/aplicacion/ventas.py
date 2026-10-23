"""Casos de uso de ventas (resumen, análisis mensual, excepciones) y tasas cambiarias."""
from datetime import timedelta

from dominio import ventas as dom
from dominio.errores import ErrorDominio
from puertos.ventas import RepositorioVentas


class CasosVentas:
    def __init__(self, repo: RepositorioVentas):
        self.repo = repo

    def excepciones_configuradas(self):
        return dom.excepciones_configuradas(self.repo.excepciones_guardadas())

    def a_excluir(self, parametro):
        """parametro = ?excluir= de la consulta (None si no vino): sin él rige la configuración guardada."""
        return self.excepciones_configuradas() if parametro is None else dom.excluir_de_parametro(parametro)

    def guardar_excepciones(self, datos):
        """{"excluir": [ids]} guarda qué excepciones se excluyen; {"restablecer": true} vuelve a las de la hoja ANAL."""
        self.repo.guardar_excepciones(None if datos.get('restablecer') else dom.validar_seleccion(datos.get('excluir')))
        return self.excepciones_configuradas()

    def resumen(self, mes, ano, excluir):
        excluir = self.a_excluir(excluir)
        total_factura, total_costo = self.repo.totales_mes(mes, ano, excluir)
        return {
            'mes': mes, 'ano': ano,
            'total_factura': round(float(total_factura), 2),
            'total_costo': round(float(total_costo), 2),
            'total_utilidad': round(float(total_factura) - float(total_costo), 2),
            'ventas_por_grupo': [{'grupo': str(g).strip().upper() if g else "SIN GRUPO", 'total': round(float(t), 2)}
                                 for g, t in self.repo.por_grupo_mes(mes, ano, excluir)],
        }

    def analisis(self, mes, ano, excluir):
        """Ventas (USD a tasa interna) de un mes por sucursal y grupo, más la tendencia de los últimos 7 días.

        Sin mes/año: el de la última venta registrada (los datos son una foto fija).
        """
        corte = self.repo.fecha_corte()
        if corte is None:
            raise ErrorDominio("No hay historial de ventas cargado.")
        mes = corte.month if mes is None else mes
        ano = corte.year if ano is None else ano
        excluir = self.a_excluir(excluir)
        principales, sucursales = dom.analisis_por_sucursal(self.repo.rentabilidad_mes(mes, ano, excluir))
        montos = self.repo.montos_excepcion(mes, ano)
        return {
            'fecha_corte': corte.isoformat(),
            'mes': mes,
            'ano': ano,
            'meses_disponibles': [{'mes': m, 'ano': a} for a, m in self.repo.meses_disponibles()],
            'total_mes': round(sum(s['total'] for s in sucursales), 2),
            'costo_mes': round(sum(s['costo'] for s in sucursales), 2),
            'utilidad_mes': round(sum(s['utilidad'] for s in sucursales), 2),
            'ventas_sin_costo_mes': round(sum(s['ventas_sin_costo'] for s in sucursales), 2),
            'total_bruto': round(float(self.repo.total_bruto(mes, ano) or 0), 2),
            'dias_sin_tasa_interna': int(self.repo.dias_sin_tasa(mes, ano) or 0),
            'excepciones': [
                {'id': e['id'], 'nombre': e['nombre'], 'categoria': e['categoria'],
                 'excluida': e['id'] in excluir, 'monto': round(float(montos.get(e['id']) or 0), 2)}
                for e in dom.EXCEPCIONES
            ],
            'grupos_principales': principales,
            'sucursales': sucursales,
            'ultimos_7_dias': dom.ultimos_dias(corte, self.repo.diarios(corte - timedelta(days=6), excluir)),
        }

    def tasas(self, fecha, dias):
        """Tasas BCV e interna vigentes en `fecha` y el historial de los `dias` anteriores."""
        def vigente(campo):
            # Última tasa registrada en o antes de la fecha (fines de semana y feriados no tienen tasa BCV propia).
            t = self.repo.tasa_vigente(fecha, campo)
            return {'fecha': t[0].isoformat(), 'valor': t[1]} if t else None

        desde, hasta = self.repo.rango_tasas()
        return {
            'fecha': fecha.isoformat(),
            'bcv': vigente('tasa_bcv'),
            'interna': vigente('tasa_paralelo'),
            'rango': {'desde': desde.isoformat() if desde else None, 'hasta': hasta.isoformat() if hasta else None},
            'historial': [{'fecha': f.isoformat(), 'bcv': float(bcv) if bcv is not None else None,
                           'interna': float(interna) if interna is not None else None}
                          for f, bcv, interna in self.repo.historial_tasas(fecha, dias)],
        }

    def guardar_tasas(self, texto):
        """Una fecha y tasa interna por línea; devuelve cuántas se guardaron."""
        tasas = dom.leer_lista_tasas(texto)
        self.repo.guardar_tasas_internas(tasas)
        return len(tasas)

    def revertir(self):
        self.repo.revertir()
