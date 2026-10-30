"""Casos de uso de traslados: orquestan el dominio y persisten mediante los puertos."""
from datetime import date, datetime

from dominio import traslados as dom
from dominio.comun import entero, texto
from dominio.errores import Conflicto, ErrorDominio, NoEncontrado
from puertos.traslados import ConsultaInventario, RepositorioTraslados


class CasosTraslados:
    def __init__(self, repo: RepositorioTraslados, inventario: ConsultaInventario, sugerencias, clasificacion_abc):
        """sugerencias(dias, comprometido_almacen) -> [dict]; clasificacion_abc() -> {código: 'A'|'B'|'C'}."""
        self.repo, self.inventario = repo, inventario
        self.sugerencias, self.clasificacion_abc = sugerencias, clasificacion_abc

    def disponibilidad(self, linea):
        existencia = self.inventario.stock_en(linea.origen, linea.articulo_codigo)
        abiertas = self.repo.lineas_abiertas(origen=linea.origen, articulo=linea.articulo_codigo)
        return existencia, dom.reservado(abiertas, linea.id)

    def obtener(self, id_):
        d = self.repo.obtener(id_)
        if d is None:
            raise NoEncontrado(f"El traslado TR-{id_:05d} no existe.")
        return d

    def eventos(self, d):
        return self.repo.eventos(d)

    def recargar(self, d):
        """Tras un error: descarta los cambios y devuelve el documento como está guardado."""
        self.repo.revertir()
        return self.repo.obtener(d.id)

    def revertir(self):
        self.repo.revertir()

    def exportacion(self, id_):
        """(nombre de archivo, filas) del traslado aprobado: código, descripción, cantidad, costo sin IVA y costo a la tasa interna."""
        d = self.obtener(id_)
        if d.estado not in dom.ESTADOS_EXPORTABLES:
            raise Conflicto('Solo se exporta un traslado aprobado.')
        hoy = date.today()
        tasa = self.inventario.tasa_interna(hoy)
        if tasa is None:
            raise Conflicto('No hay tasa interna registrada para calcular el costo.')
        lineas = sorted(dom.lineas_vigentes(d), key=dom.prioridad_linea)
        costos = self.inventario.costos([l.articulo_codigo for l in lineas])
        filas = [(l.articulo_codigo, l.articulo_nombre, dom.cantidad_vigente(l), round(costos.get(l.articulo_codigo, 0), 4),
                  round(costos.get(l.articulo_codigo, 0) * tasa, 2)) for l in lineas]
        sucursal = d.origen if d.destino == dom.ALMACEN else d.destino
        return f"{hoy:%d%m%y} TRASLADO({sucursal.upper()}).xlsx", filas

    def _guardar(self, d, eventos):
        for e in eventos:
            self.repo.agregar_evento(d, e)
        self.repo.confirmar()

    def bandeja(self, filtros, grupo, orden, pagina, por_pagina):
        if grupo not in dom.GRUPOS_ESTADO:
            raise ErrorDominio(f"grupo inválido. Opciones: {', '.join(dom.GRUPOS_ESTADO)}.")
        por_pagina = min(max(por_pagina, 1), 100)
        por_estado = self.repo.conteo_por_estado(filtros)
        conteos = {g: sum(por_estado.get(e, 0) for e in estados) for g, estados in dom.GRUPOS_ESTADO.items()}
        estados = dom.GRUPOS_ESTADO[grupo]
        total = self.repo.contar(filtros, estados)
        paginas = max((total + por_pagina - 1) // por_pagina, 1)
        # Si la página pedida dejó de existir (p. ej. tras aprobar el último de ella), se devuelve la última válida.
        pagina = min(max(pagina, 1), paginas)
        items = self.repo.pagina(filtros, estados, orden, (pagina - 1) * por_pagina, por_pagina)
        origenes, destinos = self.repo.rutas()
        return {'items': items, 'total': total, 'pagina': pagina, 'paginas': paginas, 'por_pagina': por_pagina,
                'conteos': conteos, 'opciones': {'origenes': origenes, 'destinos': destinos}}

    def editar(self, id_, datos, usuario):
        d = self.obtener(id_)
        dom.verificar_version(d, datos)
        eventos = dom.editar(d, datos, usuario, self.disponibilidad)
        if eventos:
            self._guardar(d, eventos)
        return d

    def retirar(self, id_, linea_id, datos, usuario):
        d = self.obtener(id_)
        dom.verificar_version(d, datos)
        self._guardar(d, [dom.retirar_linea(d, linea_id, datos, usuario)])
        return d

    def accionar(self, id_, datos, usuario):
        d = self.obtener(id_)
        dom.verificar_version(d, datos)
        self._guardar(d, [dom.aplicar_accion(d, datos.get('accion'), datos, usuario, self.disponibilidad)])
        return d

    def lote(self, accion, items, usuario):
        """Todo o nada: devuelve (procesados, errores); con errores no se guarda ningún cambio."""
        if accion not in dom.ACCIONES_EN_LOTE:
            raise ErrorDominio("Por lote solo se puede enviar a aprobación o descartar borradores.")
        if not isinstance(items, list) or not items:
            raise ErrorDominio("No se indicaron traslados.")
        errores, procesados = [], []
        for item in items:
            try:
                d = self.obtener(entero(item.get('id'), 'El id', 1))
                dom.verificar_version(d, item)
                self.repo.agregar_evento(d, dom.aplicar_accion(d, accion, item, usuario, self.disponibilidad))
                procesados.append(d)
            except ErrorDominio as e:
                errores.append({'id': item.get('id'), 'error': str(e)})
        if errores:
            self.repo.revertir()
        else:
            self.repo.confirmar()
        return procesados, errores

    def _borrador(self, tipo, origen, destino, usuario, ahora, horizonte=None):
        """Borrador abierto de la ruta al que se agregan artículos nuevos; si no hay, se crea uno."""
        d = self.repo.borrador_de_ruta(tipo, origen, destino)
        if d is not None:
            return d, False
        return self.repo.nuevo_documento(tipo=tipo, origen=origen, destino=destino, estado='borrador',
                                         horizonte_dias=horizonte, creado_por=usuario[0], creado_en=ahora,
                                         actualizado_en=ahora), True

    def generar(self, datos, usuario):
        """Convierte las sugerencias actuales en un borrador por sucursal, sin duplicar artículos con un traslado abierto."""
        dias = entero(datos.get('dias', 15), 'El horizonte', 1)
        clases = datos.get('clases') or ['A', 'B', 'C']
        if not isinstance(clases, list) or not set(clases) <= {'A', 'B', 'C'}:
            raise ErrorDominio("Las clases ABC deben ser una lista con A, B o C.")

        abiertas = self.repo.lineas_abiertas()
        sugerencias = self.sugerencias(dias, dom.comprometido_en_almacen(abiertas))
        por_destino, total = dom.propuestas_por_destino(sugerencias, abiertas, clases)

        ahora = datetime.now()
        creados = documentos = 0
        for destino, items in por_destino.items():
            d, nuevo = self._borrador('reposicion', dom.ALMACEN, destino, usuario, ahora, dias)
            lineas = self.repo.agregar_lineas(d, [dict(
                articulo_codigo=s['codigo'], articulo_nombre=s['nombre'], clasificacion_abc=s['clasificacion_abc'],
                tipo='reposicion', origen=dom.ALMACEN, destino=destino, estado='borrador',
                cantidad_sugerida=s['cantidad'], stock_origen=s['disponible_almacen'], stock_destino=s['stock_sucursal'],
                cobertura_dias=s['cobertura_dias'], horizonte_dias=dias, creado_por=usuario[0],
                creado_en=ahora, actualizado_en=ahora,
            ) for s in items])
            self.repo.agregar_evento(d, dom.evento_alta(d, nuevo, lineas, usuario,
                                                        f"Propuesta generada para cubrir {dias} días de demanda."))
            creados += len(lineas)
            documentos += 1
        self.repo.confirmar()
        return {'dias': dias, 'clases': clases, 'creados': creados, 'documentos': documentos,
                'omitidos': total - creados, 'sugerencias': total}

    def crear_retorno(self, datos, usuario):
        """Retorno de mercancía de una sucursal al almacén principal; se agrega al borrador abierto de esa ruta."""
        codigo = texto(datos.get('articulo_codigo'))
        origen = texto(datos.get('origen'))
        art = self.inventario.articulo(codigo) if codigo else None
        if art is None:
            raise ErrorDominio("El artículo no existe.")
        if not origen or origen == dom.ALMACEN:
            raise ErrorDominio("Indica la sucursal desde la que se retorna la mercancía.")
        cantidad = entero(datos.get('cantidad'), 'La cantidad', 1)
        if self.repo.lineas_abiertas(origen=origen, destino=dom.ALMACEN, articulo=codigo):
            raise Conflicto(f"Ya hay un retorno abierto de este artículo desde {origen}.")
        stock_origen = self.inventario.stock_en(origen, codigo)
        dom.validar_disponible(art.nombre, origen, cantidad, stock_origen,
                               dom.reservado(self.repo.lineas_abiertas(origen=origen, articulo=codigo)))
        ahora = datetime.now()
        d, nuevo = self._borrador('retorno', origen, dom.ALMACEN, usuario, ahora)
        lineas = self.repo.agregar_lineas(d, [dict(
            articulo_codigo=codigo, articulo_nombre=art.nombre, clasificacion_abc=self.clasificacion_abc().get(codigo, 'C'),
            tipo='retorno', origen=origen, destino=dom.ALMACEN, estado='borrador', cantidad_sugerida=cantidad,
            stock_origen=stock_origen, stock_destino=self.inventario.stock_en(dom.ALMACEN, codigo),
            creado_por=usuario[0], creado_en=ahora, actualizado_en=ahora,
        )])
        self.repo.agregar_evento(d, dom.evento_alta(d, nuevo, lineas, usuario,
                                                    texto(datos.get('comentario')) or "Retorno de mercancía estancada al almacén."))
        self.repo.confirmar()
        return d
