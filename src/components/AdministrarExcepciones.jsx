import { useEffect } from 'react';
import { Loader2, X } from 'lucide-react';
import { usd } from '../utils/formato.js';

// Ventas que no son facturación comercial (hoja ANAL). Marcadas = se excluyen de la facturación.
// La selección se guarda en el backend y aplica al análisis y al widget del dashboard.
export default function AdministrarExcepciones({ datos, guardando, onCambiar, onCerrar }) {
  const excluidas = datos.excepciones.filter((e) => e.excluida).map((e) => e.id);
  const alternar = (id) => onCambiar(excluidas.includes(id) ? excluidas.filter((x) => x !== id) : [...excluidas, id]);

  useEffect(() => {
    const conEscape = (e) => e.key === 'Escape' && onCerrar();
    document.addEventListener('keydown', conEscape);
    return () => document.removeEventListener('keydown', conEscape);
  }, [onCerrar]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 sm:items-center sm:p-4" onClick={onCerrar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-excepciones"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full overflow-y-auto rounded-t-2xl bg-white shadow-2xl sm:max-w-2xl sm:rounded-2xl"
      >
        <div className="sticky top-0 flex items-start justify-between gap-3 border-b border-slate-100 bg-white px-5 py-4">
          <div>
            <h2 id="titulo-excepciones" className="font-semibold text-slate-900">
              Administrar excepciones
            </h2>
            <p className="text-xs text-slate-500">
              Las marcadas no cuentan como facturación. Montos de {datos.mesNombre}.
            </p>
          </div>
          <button onClick={onCerrar} className="p-1 text-slate-400 hover:text-slate-700" aria-label="Cerrar">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <dl className="grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
            <div>
              <dt className="text-[11px] text-slate-500">Bruto</dt>
              <dd className="font-semibold text-slate-900">{usd(datos.total_bruto, 0)}</dd>
            </div>
            <div>
              <dt className="text-[11px] text-slate-500">Excluido</dt>
              <dd className="font-semibold text-slate-500">− {usd(datos.total_bruto - datos.total_mes, 0)}</dd>
            </div>
            <div>
              <dt className="text-[11px] text-slate-500">Facturación</dt>
              <dd className="font-semibold text-slate-900">{usd(datos.total_mes, 0)}</dd>
            </div>
          </dl>

          <fieldset disabled={guardando} className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
            {datos.excepciones.map((e) => (
              <label key={e.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-slate-50">
                <input
                  type="checkbox"
                  checked={e.excluida}
                  onChange={() => alternar(e.id)}
                  className="h-4 w-4 rounded border-slate-300 accent-slate-900"
                />
                <span className="flex-1 text-slate-700">
                  {e.nombre}
                  {e.categoria === 'servicio' && (
                    <span className="ml-1.5 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-500">
                      servicio
                    </span>
                  )}
                </span>
                <span className={`tabular-nums text-xs ${e.monto ? 'text-slate-600' : 'text-slate-300'}`}>{usd(e.monto, 0)}</span>
              </label>
            ))}
          </fieldset>

          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
            <button
              onClick={() => onCambiar(null)}
              disabled={guardando}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100 disabled:opacity-50"
            >
              Restablecer (como en ANAL)
            </button>
            <button
              onClick={() => onCambiar([])}
              disabled={guardando}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100 disabled:opacity-50"
            >
              Ver facturación bruta
            </button>
            {guardando && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
            <button
              onClick={onCerrar}
              className="ml-auto rounded-lg bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Listo
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
