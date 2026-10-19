import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Inbox, Loader2, Minus, Package, PackageCheck, Plus, RefreshCw, Truck, X } from 'lucide-react';
import Encabezado, { EstadoVacio } from './ui/Encabezado.jsx';
import Aviso from './ui/Aviso.jsx';
import Boton from './ui/Boton.jsx';
import { AbcBadge } from './Badges.jsx';
import { useAvisos } from './ui/Avisos.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import { accionTraslado, listarTraslados, obtenerTraslado } from '../services/api.js';
import { fechaHora } from './traslados/estados.js';

// Cada pestaña: qué traslados muestra (desde o hacia la ubicación del usuario) y qué acción ejecuta sobre ellos.
const PESTANAS = {
  despachar: {
    texto: 'Por despachar', permiso: 'despachar_mercancia', grupo: 'por_despachar', filtro: 'origen',
    accion: 'despachar', boton: 'Registrar despacho', icono: Truck, varianteBoton: 'bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800',
    etiqueta: 'Despachada', referencia: { etiqueta: 'Aprobada', campo: 'cantidad_aprobada' },
    vacio: 'No hay traslados aprobados para despachar desde tu ubicación.',
    exito: (d) => `${d.folio} despachado: queda en tránsito hacia ${d.destino}.`,
  },
  recibir: {
    texto: 'En tránsito', permiso: 'recibir_mercancia', grupo: 'en_transito', filtro: 'destino',
    accion: 'recibir', boton: 'Confirmar recepción', icono: PackageCheck, varianteBoton: 'bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800',
    etiqueta: 'Recibida', referencia: { etiqueta: 'Despachada', campo: 'cantidad_despachada' },
    vacio: 'No hay mercancía en camino hacia tu ubicación.',
    exito: (d) => (d.estado === 'recibido_con_diferencias' ? `${d.folio} recibido con diferencias: queda para revisión.` : `${d.folio} recibido completo.`),
  },
};

function TarjetaTraslado({ d, pestana, onAccion }) {
  const { icono: Icono, boton, varianteBoton } = PESTANAS[pestana];
  const resto = d.total_articulos - d.articulos.length;
  return (
    <article className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-sm font-bold text-slate-900">{d.folio}</span>
        <span className="text-xs text-slate-400">{fechaHora(d.actualizado_en)}</span>
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-1.5 text-base text-slate-700">
        {d.origen} <ArrowRight className="h-4 w-4 text-slate-400" aria-label="hacia" /> <strong className="font-semibold text-slate-900">{d.destino}</strong>
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-center">
        <div className="rounded-xl bg-slate-50 py-2">
          <p className="text-2xl font-bold tabular-nums text-slate-900">{d.total_articulos}</p>
          <p className="text-xs text-slate-500">{d.total_articulos === 1 ? 'artículo' : 'artículos'}</p>
        </div>
        <div className="rounded-xl bg-slate-50 py-2">
          <p className="text-2xl font-bold tabular-nums text-slate-900">{d.total_unidades}</p>
          <p className="text-xs text-slate-500">unidades</p>
        </div>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-slate-500">
        {d.articulos.join(', ')}
        {resto > 0 && ` y ${resto} más`}
      </p>
      <button
        onClick={() => onAccion(d)}
        className={`mt-4 flex min-h-14 w-full items-center justify-center gap-2 rounded-xl px-4 text-base font-semibold text-white transition focus:outline-none focus-visible:ring-4 focus-visible:ring-slate-300 ${varianteBoton}`}
      >
        <Icono className="h-5 w-5" /> {boton}
      </button>
    </article>
  );
}

// Ajuste de cantidad apto para el dedo: botones grandes de restar y sumar alrededor del número.
function Cantidad({ valor, onCambiar, maximo, etiqueta }) {
  const n = Number(valor);
  const boton = 'flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 active:bg-slate-200 disabled:opacity-40';
  return (
    <div className="flex items-center gap-1.5">
      <button type="button" className={boton} onClick={() => onCambiar(String(Math.max(n - 1, 0)))} disabled={n <= 0} aria-label={`Restar 1 a ${etiqueta}`}>
        <Minus className="h-5 w-5" />
      </button>
      <input
        type="number"
        inputMode="numeric"
        min={0}
        max={maximo}
        value={valor}
        onChange={(e) => onCambiar(e.target.value)}
        aria-label={etiqueta}
        className="h-11 w-16 rounded-xl border border-slate-300 text-center text-lg font-semibold tabular-nums focus:outline-none focus:ring-2 focus:ring-slate-900"
      />
      <button
        type="button"
        className={boton}
        onClick={() => onCambiar(String(n + 1))}
        disabled={maximo != null && n >= maximo}
        aria-label={`Sumar 1 a ${etiqueta}`}
      >
        <Plus className="h-5 w-5" />
      </button>
    </div>
  );
}

// Confirmación previa a despachar o recibir: evita toques accidentales y permite ajustar lo que realmente se mueve.
function HojaConfirmacion({ id, pestana, onCerrar, onHecho }) {
  const config = PESTANAS[pestana];
  const [d, setD] = useState(null);
  const [cantidades, setCantidades] = useState({});
  const [comentario, setComentario] = useState('');
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    obtenerTraslado(id)
      .then((t) => {
        setD(t);
        setCantidades(Object.fromEntries(t.lineas.map((l) => [l.id, String(l[config.referencia.campo])])));
      })
      .catch((e) => setError(e.message));
  }, [id, config.referencia.campo]);

  useEffect(() => {
    const conEscape = (e) => e.key === 'Escape' && !enviando && onCerrar();
    document.addEventListener('keydown', conEscape);
    return () => document.removeEventListener('keydown', conEscape);
  }, [enviando, onCerrar]);

  const diferentes = d ? d.lineas.filter((l) => Number(cantidades[l.id]) !== l[config.referencia.campo]) : [];
  const pideComentario = pestana === 'recibir' && diferentes.length > 0;

  const confirmar = async () => {
    for (const l of d.lineas) {
      const v = cantidades[l.id];
      if (v === '' || !Number.isInteger(Number(v)) || Number(v) < 0) return setError(`Revisa la cantidad de ${l.articulo_nombre}.`);
      if (pestana === 'despachar' && Number(v) > l.cantidad_aprobada) {
        return setError(`${l.articulo_nombre}: no se puede despachar más de lo aprobado (${l.cantidad_aprobada}).`);
      }
    }
    if (pideComentario && comentario.trim().length < 3) return setError('Describe qué llegó distinto a lo despachado.');
    setEnviando(true);
    setError(null);
    try {
      const nuevo = await accionTraslado(d.id, config.accion, d.version, {
        cantidades: Object.fromEntries(d.lineas.map((l) => [l.id, Number(cantidades[l.id])])),
        comentario: comentario.trim(),
      });
      onHecho(nuevo);
    } catch (e) {
      setError(e.message);
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 sm:items-center sm:p-4" onClick={() => !enviando && onCerrar()}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="hoja-titulo"
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[92vh] w-full flex-col rounded-t-3xl bg-white shadow-2xl sm:max-w-lg sm:rounded-3xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 id="hoja-titulo" className="text-lg font-semibold text-slate-900">
              {config.boton} {d && <span className="font-mono">{d.folio}</span>}
            </h2>
            {d && (
              <p className="text-sm text-slate-500">
                {d.origen} → {d.destino}
              </p>
            )}
          </div>
          <button onClick={onCerrar} disabled={enviando} aria-label="Cerrar" className="rounded-xl p-2 text-slate-400 hover:bg-slate-100">
            <X className="h-6 w-6" />
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {!d && !error && <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />}
          {d && (
            <>
              <p className="text-sm text-slate-600">
                {pestana === 'despachar'
                  ? 'Confirma lo que sale del almacén. Si algún artículo no se envía completo, ajusta su cantidad.'
                  : 'Cuenta la mercancía al recibirla. Ajusta solo lo que llegó distinto.'}
              </p>
              <ul className="divide-y divide-slate-100 rounded-2xl ring-1 ring-slate-200">
                {d.lineas.map((l) => {
                  const distinto = Number(cantidades[l.id]) !== l[config.referencia.campo];
                  return (
                    <li key={l.id} className={`flex flex-wrap items-center justify-between gap-3 px-3 py-3 ${distinto ? 'bg-amber-50' : ''}`}>
                      <div className="flex min-w-0 flex-1 basis-40 items-start gap-2">
                        <AbcBadge clase={l.clasificacion_abc} />
                        <div className="min-w-0">
                          <p className="text-sm font-medium leading-snug text-slate-900">{l.articulo_nombre}</p>
                          <p className="text-xs text-slate-500">
                            {config.referencia.etiqueta}: <strong className="tabular-nums">{l[config.referencia.campo]}</strong>
                          </p>
                        </div>
                      </div>
                      <Cantidad
                        valor={cantidades[l.id] ?? ''}
                        onCambiar={(v) => {
                          setCantidades((c) => ({ ...c, [l.id]: v }));
                          setError(null);
                        }}
                        maximo={pestana === 'despachar' ? l.cantidad_aprobada : undefined}
                        etiqueta={`${config.etiqueta}: ${l.articulo_nombre}`}
                      />
                    </li>
                  );
                })}
              </ul>
              {pideComentario && (
                <Aviso tono="advertencia">
                  {diferentes.length} {diferentes.length === 1 ? 'artículo no coincide' : 'artículos no coinciden'} con lo despachado. Se
                  registrará como recepción con diferencias.
                </Aviso>
              )}
              <label className="block text-sm">
                <span className="font-medium text-slate-700">
                  Observaciones
                  {!pideComentario && <span className="font-normal text-slate-400"> (opcional)</span>}
                </span>
                <textarea
                  rows={2}
                  value={comentario}
                  onChange={(e) => {
                    setComentario(e.target.value);
                    setError(null);
                  }}
                  placeholder={pideComentario ? 'Ej.: llegaron 2 unidades dañadas' : ''}
                  className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base focus:outline-none focus:ring-2 focus:ring-slate-900"
                />
              </label>
            </>
          )}
          {error && <Aviso tono="error">{error}</Aviso>}
        </div>

        <div className="grid grid-cols-2 gap-2 border-t border-slate-100 px-5 py-4">
          <button
            onClick={onCerrar}
            disabled={enviando}
            className="min-h-14 rounded-xl bg-white text-base font-semibold text-slate-700 ring-1 ring-slate-300 active:bg-slate-100"
          >
            Cancelar
          </button>
          <button
            onClick={confirmar}
            disabled={!d || enviando}
            className={`flex min-h-14 items-center justify-center gap-2 rounded-xl text-base font-semibold text-white disabled:opacity-50 ${config.varianteBoton}`}
          >
            {enviando ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />}
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function GestionLogistica() {
  const { usuario, puede } = useAuth();
  const avisar = useAvisos();
  const pestanas = Object.keys(PESTANAS).filter((p) => puede(PESTANAS[p].permiso));
  const [pestana, setPestana] = useState(pestanas[0]);
  const [listas, setListas] = useState({});
  const [error, setError] = useState(null);
  const [confirmando, setConfirmando] = useState(null);
  const ubicacion = usuario.sucursal;

  // Carga las pestañas del usuario a la vez para mostrar cuántos pendientes tiene cada una.
  const cargar = useCallback(() => {
    Promise.all(
      Object.keys(PESTANAS).filter((p) => puede(PESTANAS[p].permiso)).map((p) =>
        listarTraslados({ grupo: PESTANAS[p].grupo, [PESTANAS[p].filtro]: ubicacion, orden: 'reciente', por_pagina: 100 }).then((r) => [p, r.items])
      )
    )
      .then((r) => {
        setListas(Object.fromEntries(r));
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [ubicacion, puede]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const items = listas[pestana];
  const config = PESTANAS[pestana];

  return (
    <div className="space-y-4">
      <Encabezado icono={Package} titulo="Despacho y recepción" subtitulo={`Traslados de ${ubicacion}.`}>
        <Boton variante="fantasma" icono={RefreshCw} onClick={cargar} aria-label="Actualizar">
          <span className="hidden sm:inline">Actualizar</span>
        </Boton>
      </Encabezado>

      {pestanas.length > 1 && (
        <div role="tablist" aria-label="Tareas" className="grid grid-cols-2 gap-2">
          {pestanas.map((p) => {
            const { texto, icono: Icono } = PESTANAS[p];
            const activo = p === pestana;
            const n = listas[p]?.length;
            return (
              <button
                key={p}
                role="tab"
                aria-selected={activo}
                onClick={() => setPestana(p)}
                className={`flex min-h-12 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold transition ${
                  activo ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 ring-1 ring-slate-200'
                }`}
              >
                <Icono className="h-4 w-4" /> {texto}
                {n != null && <span className={`rounded-full px-2 text-xs tabular-nums ${activo ? 'bg-white/20' : 'bg-slate-100'}`}>{n}</span>}
              </button>
            );
          })}
        </div>
      )}

      {error && (
        <Aviso tono="error" titulo="No se pudieron cargar los traslados" accion={<Boton tamano="sm" onClick={cargar}>Reintentar</Boton>}>
          {error}
        </Aviso>
      )}
      {!items && !error && (
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <div key={i} className="h-56 animate-pulse rounded-2xl bg-slate-200/70" />
          ))}
        </div>
      )}
      {items?.length === 0 && <EstadoVacio icono={Inbox} titulo={config.vacio} />}
      {items?.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {items.map((d) => (
            <TarjetaTraslado key={d.id} d={d} pestana={pestana} onAccion={(t) => setConfirmando(t.id)} />
          ))}
        </div>
      )}

      {confirmando != null && (
        <HojaConfirmacion
          id={confirmando}
          pestana={pestana}
          onCerrar={() => setConfirmando(null)}
          onHecho={(d) => {
            setConfirmando(null);
            avisar({ tono: d.estado === 'recibido_con_diferencias' ? 'info' : 'exito', titulo: config.exito(d) });
            cargar();
          }}
        />
      )}
    </div>
  );
}
