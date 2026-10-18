import { ArrowRight, Check, ChevronRight, Send, Truck, PackageCheck, Archive, X } from 'lucide-react';
import { AbcBadge, EstadoBadge } from '../Badges.jsx';
import Boton from '../ui/Boton.jsx';
import { cantidadVigente, fechaHora } from './estados.js';

function Ruta({ t }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-xs text-slate-500">
      {t.origen} <ArrowRight className="h-3 w-3" aria-label="hacia" /> {t.destino}
      {t.tipo === 'retorno' && <span className="rounded bg-slate-100 px-1.5 text-[10px] font-medium uppercase">retorno</span>}
    </span>
  );
}

function Cantidad({ t }) {
  const { valor, etiqueta } = cantidadVigente(t);
  return (
    <div className="text-right">
      <p className="font-semibold text-slate-900">{valor}</p>
      <p className="text-[11px] text-slate-500">
        {etiqueta}
        {t.diferencia ? <span className="font-medium text-red-700"> ({t.diferencia > 0 ? '+' : ''}{t.diferencia})</span> : null}
      </p>
    </div>
  );
}

// Acciones directas por fila. Las que requieren datos (despacho, recepción, cierre) abren el detalle.
function AccionesRapidas({ t, procesando, onAccion, onAbrir }) {
  const a = t.acciones;
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
      {a.includes('enviar') && (
        <Boton tamano="sm" icono={Send} cargando={procesando} onClick={() => onAccion(t, 'enviar')}>
          Enviar
        </Boton>
      )}
      {a.includes('aprobar') && (
        <Boton tamano="sm" variante="exito" icono={Check} cargando={procesando} onClick={() => onAccion(t, 'aprobar')}>
          Aprobar
        </Boton>
      )}
      {a.includes('rechazar') && (
        <Boton tamano="sm" variante="peligro" icono={X} disabled={procesando} onClick={() => onAccion(t, 'rechazar')}>
          Rechazar
        </Boton>
      )}
      {a.includes('despachar') && (
        <Boton tamano="sm" icono={Truck} onClick={() => onAbrir(t)}>
          Despachar
        </Boton>
      )}
      {a.includes('recibir') && (
        <Boton tamano="sm" icono={PackageCheck} onClick={() => onAbrir(t)}>
          Recibir
        </Boton>
      )}
      {a.includes('cerrar') && (
        <Boton tamano="sm" icono={Archive} onClick={() => onAbrir(t)}>
          Cerrar
        </Boton>
      )}
      <Boton tamano="sm" variante="fantasma" onClick={() => onAbrir(t)} aria-label={`Ver detalle de ${t.folio}`}>
        <ChevronRight className="h-4 w-4" />
      </Boton>
    </div>
  );
}

function Seleccion({ t, seleccion, onSeleccionar }) {
  if (t.estado !== 'borrador') return null;
  return (
    <input
      type="checkbox"
      checked={seleccion.has(t.id)}
      onChange={() => onSeleccionar(t.id)}
      onClick={(e) => e.stopPropagation()}
      aria-label={`Seleccionar ${t.folio}`}
      className="h-4 w-4 rounded border-slate-300 accent-slate-900"
    />
  );
}

export default function TablaTraslados({ items, procesando, seleccion, onSeleccionar, onSeleccionarTodos, onAccion, onAbrir, resaltado }) {
  const borradores = items.filter((t) => t.estado === 'borrador');
  const todosMarcados = borradores.length > 0 && borradores.every((t) => seleccion.has(t.id));

  return (
    <>
      {/* Escritorio */}
      <div className="hidden overflow-x-auto rounded-xl bg-white ring-1 ring-slate-200 lg:block">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-10 px-3 py-3">
                {borradores.length > 0 && (
                  <input
                    type="checkbox"
                    checked={todosMarcados}
                    onChange={() => onSeleccionarTodos(!todosMarcados)}
                    aria-label="Seleccionar todos los borradores de la página"
                    className="h-4 w-4 rounded border-slate-300 accent-slate-900"
                  />
                )}
              </th>
              <th className="px-3 py-3">Traslado</th>
              <th className="px-3 py-3">ABC</th>
              <th className="px-3 py-3">Producto</th>
              <th className="px-3 py-3 text-right" title="Existencias al generar la propuesta">
                Stock orig. / dest.
              </th>
              <th className="px-3 py-3 text-right">Cantidad</th>
              <th className="px-3 py-3">Estado</th>
              <th className="px-3 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((t) => (
              <tr
                key={t.id}
                onClick={() => onAbrir(t)}
                className={`cursor-pointer transition hover:bg-slate-50 ${resaltado === t.id ? 'bg-amber-50/60' : ''}`}
              >
                <td className="px-3 py-3">
                  <Seleccion t={t} seleccion={seleccion} onSeleccionar={onSeleccionar} />
                </td>
                <td className="px-3 py-3">
                  <p className="font-mono text-xs font-semibold text-slate-700">{t.folio}</p>
                  <p className="text-[11px] text-slate-400">{fechaHora(t.actualizado_en)}</p>
                </td>
                <td className="px-3 py-3">
                  <AbcBadge clase={t.clasificacion_abc} />
                </td>
                <td className="max-w-xs px-3 py-3">
                  <p className="truncate font-medium text-slate-900" title={t.articulo_nombre}>
                    {t.articulo_nombre}
                  </p>
                  <p className="font-mono text-xs text-slate-400">{t.articulo_codigo}</p>
                  <Ruta t={t} />
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-slate-700">
                  {t.stock_origen ?? '—'} / <span className={t.stock_destino != null && t.stock_destino < 3 ? 'font-semibold text-red-700' : ''}>{t.stock_destino ?? '—'}</span>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  <Cantidad t={t} />
                </td>
                <td className="px-3 py-3">
                  <EstadoBadge estado={t.estado} />
                </td>
                <td className="px-3 py-3">
                  <AccionesRapidas t={t} procesando={!!procesando[t.id]} onAccion={onAccion} onAbrir={onAbrir} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Móvil y tablet */}
      <div className="space-y-3 lg:hidden">
        {items.map((t) => (
          <article
            key={t.id}
            className={`rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 ${resaltado === t.id ? 'ring-2 ring-amber-300' : ''}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <Seleccion t={t} seleccion={seleccion} onSeleccionar={onSeleccionar} />
                <span className="font-mono text-xs font-semibold text-slate-700">{t.folio}</span>
              </div>
              <EstadoBadge estado={t.estado} />
            </div>
            <button onClick={() => onAbrir(t)} className="mt-2 flex w-full items-start gap-3 text-left">
              <AbcBadge clase={t.clasificacion_abc} />
              <div className="min-w-0 flex-1">
                <p className="font-medium leading-snug text-slate-900">{t.articulo_nombre}</p>
                <p className="font-mono text-xs text-slate-400">{t.articulo_codigo}</p>
                <Ruta t={t} />
              </div>
            </button>
            <dl className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
              <div>
                <dt className="text-[11px] text-slate-500">Stock origen</dt>
                <dd className="text-sm text-slate-700">{t.stock_origen ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500">Stock destino</dt>
                <dd className="text-sm text-slate-700">{t.stock_destino ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500">Cantidad</dt>
                <dd className="text-sm">
                  <Cantidad t={t} />
                </dd>
              </div>
            </dl>
            <div className="mt-3">
              <AccionesRapidas t={t} procesando={!!procesando[t.id]} onAccion={onAccion} onAbrir={onAbrir} />
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
