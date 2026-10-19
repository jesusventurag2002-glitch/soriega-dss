import { ArrowRight, Check, ChevronRight, Send, Truck, PackageCheck, Archive, X } from 'lucide-react';
import { EstadoBadge } from '../Badges.jsx';
import Boton from '../ui/Boton.jsx';
import { fechaHora } from './estados.js';

const CLASES_ABC = {
  A: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  B: 'bg-sky-50 text-sky-800 ring-sky-200',
  C: 'bg-slate-100 text-slate-600 ring-slate-200',
};

function Ruta({ d }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-sm text-slate-700">
      {d.origen} <ArrowRight className="h-3.5 w-3.5 text-slate-400" aria-label="hacia" /> <strong className="font-medium">{d.destino}</strong>
      {d.tipo === 'retorno' && <span className="rounded bg-slate-100 px-1.5 text-[10px] font-medium uppercase text-slate-600">retorno</span>}
    </span>
  );
}

// Cuántos artículos de cada clase ABC lleva el documento.
function ResumenAbc({ abc }) {
  return (
    <span className="inline-flex gap-1">
      {['A', 'B', 'C'].map(
        (c) =>
          abc?.[c] > 0 && (
            <span key={c} title={`${abc[c]} de clase ${c}`} className={`rounded px-1.5 text-[11px] font-semibold tabular-nums ring-1 ${CLASES_ABC[c]}`}>
              {c} {abc[c]}
            </span>
          )
      )}
    </span>
  );
}

function Articulos({ d }) {
  const resto = d.total_articulos - d.articulos.length;
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-slate-900">
          {d.total_articulos} {d.total_articulos === 1 ? 'artículo' : 'artículos'}
        </span>
        <ResumenAbc abc={d.abc} />
      </div>
      <p className="truncate text-xs text-slate-500" title={d.articulos.join(', ')}>
        {d.articulos.join(', ')}
        {resto > 0 && ` y ${resto} más`}
      </p>
    </div>
  );
}

function Unidades({ d }) {
  return (
    <div className="text-right">
      <p className="font-semibold tabular-nums text-slate-900">{d.total_unidades}</p>
      <p className="text-[11px] text-slate-500">
        {d.con_diferencias > 0 ? <span className="font-medium text-red-700">{d.con_diferencias} con diferencia</span> : 'unidades'}
      </p>
    </div>
  );
}

// Acciones sobre el documento completo. Las que requieren cantidades por artículo (despacho, recepción, cierre)
// abren el detalle.
function AccionesRapidas({ d, procesando, onAccion, onAbrir }) {
  const a = d.acciones;
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
      {a.includes('enviar') && (
        <Boton tamano="sm" icono={Send} cargando={procesando} onClick={() => onAccion(d, 'enviar')}>
          Enviar
        </Boton>
      )}
      {a.includes('aprobar') && (
        <Boton tamano="sm" variante="exito" icono={Check} cargando={procesando} onClick={() => onAccion(d, 'aprobar')}>
          Aprobar
        </Boton>
      )}
      {a.includes('rechazar') && (
        <Boton tamano="sm" variante="peligro" icono={X} disabled={procesando} onClick={() => onAccion(d, 'rechazar')}>
          Rechazar
        </Boton>
      )}
      {a.includes('despachar') && (
        <Boton tamano="sm" icono={Truck} onClick={() => onAbrir(d)}>
          Despachar
        </Boton>
      )}
      {a.includes('recibir') && (
        <Boton tamano="sm" icono={PackageCheck} onClick={() => onAbrir(d)}>
          Recibir
        </Boton>
      )}
      {a.includes('cerrar') && (
        <Boton tamano="sm" icono={Archive} onClick={() => onAbrir(d)}>
          Cerrar
        </Boton>
      )}
      <Boton tamano="sm" variante="fantasma" onClick={() => onAbrir(d)} aria-label={`Ver detalle de ${d.folio}`}>
        <ChevronRight className="h-4 w-4" />
      </Boton>
    </div>
  );
}

function Seleccion({ d, seleccion, onSeleccionar }) {
  if (d.estado !== 'borrador') return null;
  return (
    <input
      type="checkbox"
      checked={seleccion.has(d.id)}
      onChange={() => onSeleccionar(d.id)}
      onClick={(e) => e.stopPropagation()}
      aria-label={`Seleccionar ${d.folio}`}
      className="h-4 w-4 rounded border-slate-300 accent-slate-900"
    />
  );
}

// Una fila por documento de traslado; el detalle con los artículos se abre en el panel lateral.
export default function TablaTraslados({ items, procesando, seleccion, onSeleccionar, onSeleccionarTodos, onAccion, onAbrir, resaltado }) {
  const borradores = items.filter((d) => d.estado === 'borrador');
  const todosMarcados = borradores.length > 0 && borradores.every((d) => seleccion.has(d.id));

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
              <th className="px-3 py-3">Folio</th>
              <th className="px-3 py-3">Ruta</th>
              <th className="px-3 py-3">Artículos</th>
              <th className="px-3 py-3 text-right">Unidades</th>
              <th className="px-3 py-3">Estado</th>
              <th className="px-3 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((d) => (
              <tr
                key={d.id}
                onClick={() => onAbrir(d)}
                className={`cursor-pointer transition hover:bg-slate-50 ${resaltado === d.id ? 'bg-amber-50/60' : ''}`}
              >
                <td className="px-3 py-3">
                  <Seleccion d={d} seleccion={seleccion} onSeleccionar={onSeleccionar} />
                </td>
                <td className="whitespace-nowrap px-3 py-3">
                  <p className="font-mono text-xs font-semibold text-slate-800">{d.folio}</p>
                  <p className="text-[11px] text-slate-400">{fechaHora(d.actualizado_en)}</p>
                </td>
                <td className="px-3 py-3">
                  <Ruta d={d} />
                </td>
                <td className="max-w-xs px-3 py-3">
                  <Articulos d={d} />
                </td>
                <td className="px-3 py-3">
                  <Unidades d={d} />
                </td>
                <td className="px-3 py-3">
                  <EstadoBadge estado={d.estado} />
                </td>
                <td className="px-3 py-3">
                  <AccionesRapidas d={d} procesando={!!procesando[d.id]} onAccion={onAccion} onAbrir={onAbrir} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Móvil y tablet */}
      <div className="space-y-3 lg:hidden">
        {items.map((d) => (
          <article
            key={d.id}
            className={`rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 ${resaltado === d.id ? 'ring-2 ring-amber-300' : ''}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <Seleccion d={d} seleccion={seleccion} onSeleccionar={onSeleccionar} />
                <span className="font-mono text-xs font-semibold text-slate-800">{d.folio}</span>
              </div>
              <EstadoBadge estado={d.estado} />
            </div>
            <button onClick={() => onAbrir(d)} className="mt-2 block w-full space-y-2 text-left">
              <Ruta d={d} />
              <div className="flex items-end justify-between gap-3 rounded-lg bg-slate-50 p-3">
                <Articulos d={d} />
                <Unidades d={d} />
              </div>
            </button>
            <div className="mt-3">
              <AccionesRapidas d={d} procesando={!!procesando[d.id]} onAccion={onAccion} onAbrir={onAbrir} />
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
