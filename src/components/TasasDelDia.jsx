import { useEffect, useRef, useState } from 'react';
import { Landmark, X } from 'lucide-react';
import { obtenerTasas } from '../services/api.js';
import { fechaLocal } from '../utils/formato.js';

const tasa = (n) => (n == null ? '—' : n.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const fechaCorta = (iso) => fechaLocal(iso).toLocaleDateString('es-VE', { weekday: 'short', day: '2-digit', month: '2-digit' });

function Vigente({ etiqueta, dato, fecha }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs text-slate-500">{etiqueta}</p>
      <p className="text-xl font-bold text-slate-900">{tasa(dato?.valor)}</p>
      {/* Si la fecha elegida no tiene tasa propia (fin de semana, feriado) se indica de cuándo es */}
      {dato && dato.fecha !== fecha && (
        <p className="text-[11px] text-slate-400">vigente desde {fechaLocal(dato.fecha).toLocaleDateString('es-VE')}</p>
      )}
    </div>
  );
}

export default function TasasDelDia() {
  const [datos, setDatos] = useState(null);
  const [fecha, setFecha] = useState(null); // null = hoy
  const [abierto, setAbierto] = useState(false);
  const [error, setError] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    obtenerTasas(fecha)
      .then((d) => {
        setDatos(d);
        setError(false);
      })
      .catch(() => setError(true));
  }, [fecha]);

  // Cierra el panel al hacer clic fuera.
  useEffect(() => {
    if (!abierto) return;
    const cerrar = (e) => ref.current && !ref.current.contains(e.target) && setAbierto(false);
    document.addEventListener('mousedown', cerrar);
    return () => document.removeEventListener('mousedown', cerrar);
  }, [abierto]);

  if (error && !datos) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setAbierto((v) => !v)}
        title="Tasas del día"
        className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-200"
      >
        <Landmark className="h-4 w-4 text-slate-500" />
        {datos && !fecha ? (
          <span className="hidden sm:inline">
            BCV {tasa(datos.bcv?.valor)} · Int. {tasa(datos.interna?.valor)}
          </span>
        ) : (
          <span className="hidden sm:inline">Tasas</span>
        )}
      </button>

      {abierto && datos && (
        <div className="fixed sm:absolute inset-x-4 sm:inset-x-auto sm:right-0 top-16 sm:top-auto sm:mt-2 sm:w-96 z-40 rounded-xl bg-white shadow-2xl ring-1 ring-slate-200">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="font-semibold text-slate-900">Tasas del sistema</p>
            <button onClick={() => setAbierto(false)} className="p-1 text-slate-400 hover:text-slate-700" aria-label="Cerrar">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-3 p-4">
            <label className="flex items-center justify-between gap-3 text-sm text-slate-600">
              Fecha
              <input
                type="date"
                value={datos.fecha}
                min={datos.rango.desde ?? undefined}
                max={datos.rango.hasta ?? undefined}
                onChange={(e) => e.target.value && setFecha(e.target.value)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
              />
            </label>

            <div className="grid grid-cols-2 gap-2">
              <Vigente etiqueta="Tasa BCV" dato={datos.bcv} fecha={datos.fecha} />
              <Vigente etiqueta="Tasa interna" dato={datos.interna} fecha={datos.fecha} />
            </div>

            <div className="max-h-56 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th className="py-1.5">Fecha</th>
                    <th className="py-1.5 text-right">BCV</th>
                    <th className="py-1.5 text-right">Interna</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 tabular-nums">
                  {datos.historial.map((h) => (
                    <tr key={h.fecha} className={h.fecha === datos.fecha ? 'bg-slate-50 font-medium' : ''}>
                      <td className="py-1.5 capitalize text-slate-600">{fechaCorta(h.fecha)}</td>
                      <td className="py-1.5 text-right text-slate-900">{tasa(h.bcv)}</td>
                      <td className="py-1.5 text-right text-slate-900">{tasa(h.interna)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {datos.historial.length === 0 && (
                <p className="py-4 text-center text-xs text-slate-400">Sin tasas registradas para esta fecha.</p>
              )}
            </div>

            <p className="text-[11px] text-slate-400">
              BCV: factor del sistema en el reporte de ventas. Interna: hoja TASA (Configuración inicial). Ambas
              llegarán del sistema administrativo con la conexión ODBC.
            </p>
            {fecha && (
              <button onClick={() => setFecha(null)} className="text-xs font-medium text-slate-600 underline underline-offset-2">
                Volver a hoy
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
