import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, Clock, AlertTriangle, Truck, Flame, AlertOctagon, ChevronRight, ClipboardX } from 'lucide-react';
import { obtenerDashboard } from '../services/api.js';
import { useAuth } from '../auth/AuthContext.jsx';

// Alertas operativas calculadas en el backend; cada una lleva a los registros que la componen.
// Solo se incluyen las que llevan a una vista que el usuario puede abrir.
function construirAlertas(d, puede) {
  const t = d.traslados;
  const discrepancias = puede('revisar_discrepancias') && d.discrepancias_pendientes > 0 && {
    id: 'discrepancias', icono: ClipboardX, color: 'text-red-700 bg-red-50',
    titulo: `${d.discrepancias_pendientes} ${d.discrepancias_pendientes === 1 ? 'discrepancia reportada' : 'discrepancias reportadas'} por el piso de venta`,
    destino: { vista: 'discrepancias' },
  };
  if (!puede('traslados')) return [discrepancias].filter(Boolean);
  return [
    discrepancias,
    t.por_aprobar > 0 && {
      id: 'aprobar', icono: Clock, color: 'text-amber-700 bg-amber-50',
      titulo: `${t.por_aprobar} ${t.por_aprobar === 1 ? 'traslado espera' : 'traslados esperan'} aprobación`,
      destino: { vista: 'traslados', filtros: { grupo: 'por_aprobar' } },
    },
    t.con_diferencias > 0 && {
      id: 'diferencias', icono: AlertTriangle, color: 'text-red-700 bg-red-50',
      titulo: `${t.con_diferencias} ${t.con_diferencias === 1 ? 'recepción' : 'recepciones'} con diferencias por conciliar`,
      destino: { vista: 'traslados', filtros: { grupo: 'por_cerrar' } },
    },
    t.en_transito > 0 && {
      id: 'transito', icono: Truck, color: 'text-indigo-700 bg-indigo-50',
      titulo: `${t.en_transito} ${t.en_transito === 1 ? 'traslado' : 'traslados'} en tránsito por recibir`,
      destino: { vista: 'traslados', filtros: { grupo: 'en_transito' } },
    },
    d.criticos.total > 0 && {
      id: 'criticos', icono: Flame, color: 'text-red-700 bg-red-50',
      titulo: `${d.criticos.total} productos A/B con menos de ${d.criticos.dias_cobertura} días de cobertura`,
      destino: { vista: 'inicio' },
    },
    d.acciones_estancado.pendientes > 0 && {
      id: 'estancado', icono: AlertOctagon, color: 'text-slate-700 bg-slate-100',
      titulo: `${d.acciones_estancado.pendientes} acciones sobre mercancía estancada en curso`,
      destino: { vista: 'estancado' },
    },
  ].filter(Boolean);
}

export default function AlertBell({ vista, onIr }) {
  const { puede } = useAuth();
  const [alertas, setAlertas] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const ref = useRef(null);

  const cargar = useCallback(() => {
    obtenerDashboard()
      .then((d) => setAlertas(construirAlertas(d, puede)))
      .catch(() => setAlertas(null)); // sin backend no se muestran alertas inventadas
  }, [puede]);

  // Se actualiza al cambiar de módulo y al abrir el panel.
  useEffect(() => {
    cargar();
  }, [cargar, vista]);

  useEffect(() => {
    if (!abierto) return undefined;
    const cerrar = (e) => ref.current && !ref.current.contains(e.target) && setAbierto(false);
    const conEscape = (e) => e.key === 'Escape' && setAbierto(false);
    document.addEventListener('mousedown', cerrar);
    document.addEventListener('keydown', conEscape);
    return () => {
      document.removeEventListener('mousedown', cerrar);
      document.removeEventListener('keydown', conEscape);
    };
  }, [abierto]);

  const n = alertas?.length ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => {
          if (!abierto) cargar();
          setAbierto((v) => !v);
        }}
        className="relative rounded-lg p-2 text-slate-600 transition hover:bg-slate-100"
        aria-label={n ? `Alertas: ${n} pendientes` : 'Alertas'}
        aria-expanded={abierto}
      >
        <Bell className="h-5 w-5" />
        {n > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white ring-2 ring-white">
            {n}
          </span>
        )}
      </button>

      {abierto && (
        <div className="fixed inset-x-4 top-16 z-40 overflow-hidden rounded-xl bg-white shadow-2xl ring-1 ring-slate-200 sm:absolute sm:inset-x-auto sm:right-0 sm:top-auto sm:mt-2 sm:w-96">
          <p className="border-b border-slate-100 px-4 py-3 font-semibold text-slate-900">Requiere atención</p>
          {alertas === null && <p className="px-4 py-6 text-center text-sm text-slate-500">No se pudieron obtener las alertas.</p>}
          {alertas?.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-500">No hay alertas pendientes.</p>}
          <ul className="divide-y divide-slate-100">
            {alertas?.map((a) => {
              const Icono = a.icono;
              return (
                <li key={a.id}>
                  <button
                    onClick={() => {
                      setAbierto(false);
                      onIr(a.destino);
                    }}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50"
                  >
                    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${a.color}`}>
                      <Icono className="h-4 w-4" />
                    </span>
                    <span className="flex-1 text-sm text-slate-800">{a.titulo}</span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
