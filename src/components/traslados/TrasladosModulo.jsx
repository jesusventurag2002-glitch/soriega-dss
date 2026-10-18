import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeftRight, ChevronLeft, ChevronRight, Inbox, Search, Send, Sparkles, Trash2, X } from 'lucide-react';
import Encabezado, { EstadoVacio } from '../ui/Encabezado.jsx';
import Boton from '../ui/Boton.jsx';
import Aviso from '../ui/Aviso.jsx';
import Dialogo from '../ui/Dialogo.jsx';
import PanelLateral from '../ui/PanelLateral.jsx';
import { useAvisos } from '../ui/Avisos.jsx';
import TablaTraslados from './TablaTraslados.jsx';
import DetalleTraslado from './DetalleTraslado.jsx';
import { GRUPOS, GRUPO_DE_ESTADO, MENSAJE_ACCION, SIGUIENTE_PASO } from './estados.js';
import { accionTraslado, editarTraslado, generarTraslados, listarTraslados, loteTraslados } from '../../services/api.js';

export const FILTROS_INICIALES = { grupo: 'activos', q: '', sucursal: '', origen: '', destino: '', abc: '', orden: 'prioridad', pagina: 1 };

const HORIZONTES = [7, 15, 30];
const ORDENES = [
  { id: 'prioridad', texto: 'Prioridad (ABC y cobertura)' },
  { id: 'reciente', texto: 'Actualizados recientemente' },
  { id: 'estado', texto: 'Estado' },
  { id: 'cantidad', texto: 'Cantidad (mayor primero)' },
  { id: 'producto', texto: 'Producto (A–Z)' },
];
const VERBO = {
  enviar: 'enviar', descartar: 'descartar', aprobar: 'aprobar', rechazar: 'rechazar',
  despachar: 'despachar', recibir: 'registrar la recepción de', cerrar: 'cerrar',
};
const folioDe = (id) => `TR-${String(id).padStart(5, '0')}`;
const claseSelect =
  'rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900';

export default function TrasladosModulo({ filtros, onFiltros, detalleId, onDetalle }) {
  const avisar = useAvisos();
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [procesando, setProcesando] = useState({});
  const [seleccion, setSeleccion] = useState(() => new Set());
  const [dias, setDias] = useState(15);
  const [generando, setGenerando] = useState(false);
  const [busqueda, setBusqueda] = useState(filtros.q);
  const [dialogo, setDialogo] = useState(null);
  const [resaltado, setResaltado] = useState(null);
  const ultimaSolicitud = useRef(0);

  const cambiarFiltros = useCallback(
    (cambios) => onFiltros((f) => ({ ...f, ...cambios, pagina: cambios.pagina ?? 1 })),
    [onFiltros]
  );

  // La búsqueda se aplica al dejar de escribir.
  useEffect(() => {
    if (busqueda === filtros.q) return undefined;
    const t = setTimeout(() => cambiarFiltros({ q: busqueda }), 350);
    return () => clearTimeout(t);
  }, [busqueda, filtros.q, cambiarFiltros]);

  const cargar = useCallback(async () => {
    const solicitud = ++ultimaSolicitud.current;
    setCargando(true);
    try {
      const d = await listarTraslados({ ...filtros, por_pagina: 25 });
      if (solicitud !== ultimaSolicitud.current) return; // llegó después de otra más reciente
      setDatos(d);
      setError(null);
      // Si la página quedó vacía (p. ej. tras aprobar el último registro), el servidor devuelve la última válida.
      if (d.pagina !== filtros.pagina) onFiltros((f) => ({ ...f, pagina: d.pagina }));
    } catch (e) {
      if (solicitud === ultimaSolicitud.current) setError(e.message);
    } finally {
      if (solicitud === ultimaSolicitud.current) setCargando(false);
    }
  }, [filtros, onFiltros]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // La selección por lote solo vale para la vista en la que se hizo.
  useEffect(() => setSeleccion(new Set()), [filtros]);

  const reemplazar = (t) => setDatos((d) => d && { ...d, items: d.items.map((i) => (i.id === t.id ? { ...i, ...t } : i)) });
  const marcarProcesando = (id, valor) =>
    setProcesando((p) => {
      const copia = { ...p };
      if (valor) copia[id] = true;
      else delete copia[id];
      return copia;
    });

  // Ejecuta una transición: actualiza solo esa fila, avisa y luego refresca conteos sin perder filtros ni página.
  const ejecutar = useCallback(
    async (t, accion, extra = {}) => {
      marcarProcesando(t.id, true);
      try {
        const nuevo = await accionTraslado(t.id, accion, t.version, extra);
        reemplazar(nuevo);
        setResaltado(nuevo.id);
        avisar({
          tono: 'exito',
          titulo: `${nuevo.folio} ${nuevo.estado === 'recibido_con_diferencias' ? 'recibido con diferencias' : MENSAJE_ACCION[accion]}`,
          texto: `${SIGUIENTE_PASO[nuevo.estado]} Está en «${GRUPO_DE_ESTADO[nuevo.estado]}».`,
          accion: detalleId === nuevo.id ? undefined : { texto: 'Ver detalle', onClick: () => onDetalle(nuevo.id) },
        });
        cargar();
        return nuevo;
      } catch (e) {
        // Ante un conflicto se muestra el estado real del servidor, nunca el que se intentó aplicar.
        if (e.cuerpo?.traslado) {
          reemplazar(e.cuerpo.traslado);
          cargar();
        }
        avisar({ tono: 'error', titulo: `No se pudo ${VERBO[accion]} ${t.folio}`, texto: e.message });
        throw e;
      } finally {
        marcarProcesando(t.id, false);
      }
    },
    [avisar, cargar, detalleId, onDetalle]
  );

  const editar = useCallback(
    async (t, cambios) => {
      marcarProcesando(t.id, true);
      try {
        const nuevo = await editarTraslado(t.id, t.version, cambios);
        reemplazar(nuevo);
        avisar({ tono: 'exito', titulo: `${nuevo.folio} actualizado`, texto: 'El cambio quedó registrado en el historial.' });
        return nuevo;
      } catch (e) {
        if (e.cuerpo?.traslado) reemplazar(e.cuerpo.traslado);
        avisar({ tono: 'error', titulo: `No se pudo actualizar ${t.folio}`, texto: e.message });
        throw e;
      } finally {
        marcarProcesando(t.id, false);
      }
    },
    [avisar]
  );

  // Acciones rápidas de la tabla; rechazar siempre pide el motivo.
  const accionRapida = (t, accion) => {
    if (accion === 'rechazar') {
      setDialogo({
        titulo: `Rechazar ${t.folio}`,
        texto: `${t.articulo_nombre} · ${t.cantidad_sugerida} u de ${t.origen} a ${t.destino}.`,
        textoConfirmar: 'Rechazar',
        variante: 'peligro',
        campo: { etiqueta: 'Motivo del rechazo', requerido: true, placeholder: 'Ej.: hay una compra en camino' },
        accion: (motivo) => ejecutar(t, 'rechazar', { motivo }),
      });
      return;
    }
    ejecutar(t, accion).catch(() => {});
  };

  const generar = async () => {
    setGenerando(true);
    try {
      const r = await generarTraslados(dias);
      avisar({
        tono: r.creados ? 'exito' : 'info',
        titulo: r.creados ? `${r.creados} propuestas nuevas` : 'No hay propuestas nuevas',
        texto: r.message,
        accion: r.creados ? { texto: 'Ver borradores', onClick: () => cambiarFiltros({ grupo: 'borradores' }) } : undefined,
      });
      cargar();
    } catch (e) {
      avisar({ tono: 'error', titulo: 'No se pudieron generar propuestas', texto: e.message });
    } finally {
      setGenerando(false);
    }
  };

  const seleccionados = datos ? datos.items.filter((t) => seleccion.has(t.id)) : [];
  const confirmarLote = (accion) =>
    setDialogo({
      titulo: accion === 'enviar' ? `Enviar ${seleccionados.length} borradores a aprobación` : `Descartar ${seleccionados.length} borradores`,
      texto: (
        <>
          <p>Se aplicará a estos traslados (todos o ninguno):</p>
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto rounded-lg bg-slate-50 p-2 text-xs">
            {seleccionados.map((t) => (
              <li key={t.id} className="flex justify-between gap-2">
                <span className="truncate">
                  <span className="font-mono">{t.folio}</span> · {t.articulo_nombre} → {t.destino}
                </span>
                <span className="shrink-0 font-semibold tabular-nums">{t.cantidad_sugerida} u</span>
              </li>
            ))}
          </ul>
        </>
      ),
      textoConfirmar: accion === 'enviar' ? 'Enviar a aprobación' : 'Descartar',
      variante: accion === 'enviar' ? 'primario' : 'peligro',
      campo: accion === 'descartar' ? { etiqueta: 'Motivo', requerido: false } : undefined,
      accion: async (comentario) => {
        try {
          await loteTraslados(accion, seleccionados.map((t) => ({ id: t.id, version: t.version, comentario })));
        } catch (e) {
          const detalle = (e.cuerpo?.errores ?? []).map((x) => x.error).join(' ');
          throw new Error(`${e.message} ${detalle}`.trim());
        }
        avisar({
          tono: 'exito',
          titulo: `${seleccionados.length} traslados ${accion === 'enviar' ? 'enviados a aprobación' : 'descartados'}`,
          texto: accion === 'enviar' ? 'Quedan en «Por aprobar» a la espera de un gerente.' : undefined,
        });
        setSeleccion(new Set());
        cargar();
      },
    });

  const hayFiltros = filtros.q || filtros.sucursal || filtros.origen || filtros.destino || filtros.abc;
  const opciones = datos?.opciones ?? { origenes: [], destinos: [] };
  const detalleEnLista = datos?.items.find((t) => t.id === detalleId);

  return (
    <div className="space-y-5">
      <Encabezado
        icono={ArrowLeftRight}
        titulo="Traslados"
        subtitulo="Propuestas entre el almacén y las sucursales, y su seguimiento hasta la recepción."
      >
        <label className="sr-only" htmlFor="horizonte">
          Días de demanda a cubrir
        </label>
        <select id="horizonte" value={dias} onChange={(e) => setDias(Number(e.target.value))} className={claseSelect}>
          {HORIZONTES.map((d) => (
            <option key={d} value={d}>
              Cubrir {d} días
            </option>
          ))}
        </select>
        <Boton variante="primario" icono={Sparkles} cargando={generando} onClick={generar}>
          Generar propuestas
        </Boton>
      </Encabezado>

      <div role="tablist" aria-label="Estado de los traslados" className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        {GRUPOS.map((g) => {
          const activo = filtros.grupo === g.id;
          const n = datos?.conteos?.[g.id];
          return (
            <button
              key={g.id}
              role="tab"
              aria-selected={activo}
              onClick={() => cambiarFiltros({ grupo: g.id })}
              className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                activo ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
              }`}
            >
              {g.texto}
              {n != null && (
                <span className={`rounded-full px-1.5 text-xs tabular-nums ${activo ? 'bg-white/20' : 'bg-slate-100 text-slate-500'}`}>{n}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto_auto_auto]">
        <label className="relative sm:col-span-2 lg:col-span-1">
          <span className="sr-only">Buscar por producto, código o folio</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar producto, código o folio (TR-…)"
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </label>
        <select aria-label="Origen" value={filtros.origen} onChange={(e) => cambiarFiltros({ origen: e.target.value })} className={claseSelect}>
          <option value="">Todos los orígenes</option>
          {opciones.origenes.map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
        <select aria-label="Destino" value={filtros.destino} onChange={(e) => cambiarFiltros({ destino: e.target.value })} className={claseSelect}>
          <option value="">Todos los destinos</option>
          {opciones.destinos.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
        <select aria-label="Clasificación ABC" value={filtros.abc} onChange={(e) => cambiarFiltros({ abc: e.target.value })} className={claseSelect}>
          <option value="">ABC: todas</option>
          <option value="A">Clase A</option>
          <option value="B">Clase B</option>
          <option value="C">Clase C</option>
        </select>
        <select aria-label="Ordenar por" value={filtros.orden} onChange={(e) => cambiarFiltros({ orden: e.target.value })} className={claseSelect}>
          {ORDENES.map((o) => (
            <option key={o.id} value={o.id}>
              {o.texto}
            </option>
          ))}
        </select>
        {hayFiltros ? (
          <Boton
            variante="fantasma"
            icono={X}
            onClick={() => {
              setBusqueda('');
              cambiarFiltros({ q: '', sucursal: '', origen: '', destino: '', abc: '' });
            }}
          >
            Limpiar
          </Boton>
        ) : (
          <span className="hidden lg:block" />
        )}
      </div>

      {filtros.sucursal && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          Mostrando traslados de
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white">
            {filtros.sucursal} (origen o destino)
            <button onClick={() => cambiarFiltros({ sucursal: '' })} aria-label="Quitar filtro de sucursal" className="rounded-full hover:bg-white/20">
              <X className="h-3.5 w-3.5" />
            </button>
          </span>
        </p>
      )}

      {error && (
        <Aviso tono="error" titulo="No se pudieron cargar los traslados" accion={<Boton tamano="sm" onClick={cargar}>Reintentar</Boton>}>
          {error}
        </Aviso>
      )}

      {seleccionados.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm text-white">
          <span>
            {seleccionados.length} {seleccionados.length === 1 ? 'borrador seleccionado' : 'borradores seleccionados'}
          </span>
          <div className="flex flex-wrap gap-2">
            <Boton tamano="sm" icono={Send} onClick={() => confirmarLote('enviar')}>
              Enviar a aprobación
            </Boton>
            <Boton tamano="sm" variante="peligro" icono={Trash2} onClick={() => confirmarLote('descartar')}>
              Descartar
            </Boton>
            <Boton tamano="sm" variante="fantasma" className="text-white hover:bg-white/10 hover:text-white" onClick={() => setSeleccion(new Set())}>
              Quitar selección
            </Boton>
          </div>
        </div>
      )}

      {!datos && !error && (
        <div className="space-y-3" aria-label="Cargando traslados">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-slate-200/70" />
          ))}
        </div>
      )}

      {datos && datos.items.length === 0 && (
        <EstadoVacio icono={Inbox} titulo={hayFiltros ? 'Ningún traslado coincide con los filtros' : 'No hay traslados en esta vista'}>
          {hayFiltros
            ? 'Prueba con otros términos o limpia los filtros.'
            : datos.conteos.todos === 0
              ? 'Usa «Generar propuestas» para crear borradores a partir del inventario y las ventas cargadas.'
              : 'Revisa las otras pestañas.'}
        </EstadoVacio>
      )}

      {datos && datos.items.length > 0 && (
        // Al recargar se mantiene la tabla visible (atenuada) para no perder la posición.
        <div className={`space-y-3 transition-opacity ${cargando ? 'opacity-60' : ''}`} aria-busy={cargando}>
          <TablaTraslados
            items={datos.items}
            procesando={procesando}
            seleccion={seleccion}
            resaltado={resaltado}
            onSeleccionar={(id) =>
              setSeleccion((s) => {
                const copia = new Set(s);
                if (copia.has(id)) copia.delete(id);
                else copia.add(id);
                return copia;
              })
            }
            onSeleccionarTodos={(todos) =>
              setSeleccion(todos ? new Set(datos.items.filter((t) => t.estado === 'borrador').map((t) => t.id)) : new Set())
            }
            onAccion={accionRapida}
            onAbrir={(t) => onDetalle(t.id)}
          />

          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
            <span>
              {datos.total} {datos.total === 1 ? 'traslado' : 'traslados'} · página {datos.pagina} de {datos.paginas}
            </span>
            {datos.paginas > 1 && (
              <div className="flex gap-2">
                <Boton tamano="sm" icono={ChevronLeft} disabled={datos.pagina <= 1} onClick={() => cambiarFiltros({ pagina: datos.pagina - 1 })}>
                  Anterior
                </Boton>
                <Boton tamano="sm" disabled={datos.pagina >= datos.paginas} onClick={() => cambiarFiltros({ pagina: datos.pagina + 1 })}>
                  Siguiente <ChevronRight className="h-3.5 w-3.5" />
                </Boton>
              </div>
            )}
          </div>
        </div>
      )}

      <PanelLateral
        abierto={detalleId != null}
        titulo={detalleId != null ? `Traslado ${folioDe(detalleId)}` : ''}
        subtitulo="Detalle, acciones e historial"
        onCerrar={() => onDetalle(null)}
      >
        {detalleId != null && (
          <DetalleTraslado
            id={detalleId}
            version={detalleEnLista?.version}
            ejecutar={ejecutar}
            editar={editar}
            procesando={!!procesando[detalleId]}
          />
        )}
      </PanelLateral>

      {dialogo && (
        <Dialogo
          titulo={dialogo.titulo}
          textoConfirmar={dialogo.textoConfirmar}
          varianteConfirmar={dialogo.variante}
          campo={dialogo.campo}
          onCancelar={() => setDialogo(null)}
          onConfirmar={async (texto) => {
            await dialogo.accion(texto);
            setDialogo(null);
          }}
        >
          {dialogo.texto}
        </Dialogo>
      )}
    </div>
  );
}
