import { useEffect, useRef, useState } from 'react';
import { Bell, AlertTriangle, TrendingDown, RefreshCw } from 'lucide-react';
import { ALERTAS } from '../data/mockData.js';

const ICONOS = {
  discrepancia: { icono: AlertTriangle, color: 'text-red-600 bg-red-50' },
  quiebre: { icono: TrendingDown, color: 'text-amber-600 bg-amber-50' },
  sync: { icono: RefreshCw, color: 'text-emerald-600 bg-emerald-50' },
};

export default function AlertBell() {
  const [alertas, setAlertas] = useState(ALERTAS);
  const [abierto, setAbierto] = useState(false);
  const ref = useRef(null);

  const noLeidas = alertas.filter((a) => !a.leida).length;

  // Cierra el panel al hacer clic fuera.
  useEffect(() => {
    if (!abierto) return;
    const cerrar = (e) => ref.current && !ref.current.contains(e.target) && setAbierto(false);
    document.addEventListener('mousedown', cerrar);
    return () => document.removeEventListener('mousedown', cerrar);
  }, [abierto]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setAbierto((v) => !v)}
        className="relative p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition"
        aria-label="Alertas"
      >
        <Bell className="h-5 w-5" />
        {noLeidas > 0 && (
          <span className="absolute -top-0.5 -right-0.5 h-5 min-w-5 px-1 rounded-full bg-red-600 text-[10px] font-bold text-white flex items-center justify-center ring-2 ring-white animate-pulse">
            {noLeidas}
          </span>
        )}
      </button>

      {abierto && (
        <div className="fixed sm:absolute inset-x-4 sm:inset-x-auto sm:right-0 top-16 sm:top-auto sm:mt-2 sm:w-96 bg-white rounded-xl shadow-2xl ring-1 ring-slate-200 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <p className="font-semibold text-slate-900">Alertas de auditoría</p>
            {noLeidas > 0 && (
              <button
                onClick={() => setAlertas((prev) => prev.map((a) => ({ ...a, leida: true })))}
                className="text-xs font-medium text-slate-500 hover:text-slate-900"
              >
                Marcar todas como leídas
              </button>
            )}
          </div>
          <ul className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
            {alertas.map((a) => {
              const { icono: Icono, color } = ICONOS[a.tipo];
              return (
                <li key={a.id} className={`flex gap-3 px-4 py-3 ${a.leida ? '' : 'bg-slate-50'}`}>
                  <div className={`h-9 w-9 shrink-0 rounded-lg flex items-center justify-center ${color}`}>
                    <Icono className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 flex items-center gap-2">
                      {a.titulo}
                      {!a.leida && <span className="h-2 w-2 rounded-full bg-red-500" />}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">{a.detalle}</p>
                    <p className="text-[11px] text-slate-400 mt-1">{a.hace}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
