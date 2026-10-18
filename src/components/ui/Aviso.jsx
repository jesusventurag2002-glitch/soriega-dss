import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';

// Significado fijo de los colores en toda la app: verde = completado, ámbar = advertencia/pendiente,
// rojo = error/incidencia, gris azulado = información. Siempre con icono y texto, nunca solo color.
export const TONOS = {
  exito: { icono: CheckCircle2, clase: 'bg-emerald-50 text-emerald-800 ring-emerald-200', iconoClase: 'text-emerald-600' },
  advertencia: { icono: AlertTriangle, clase: 'bg-amber-50 text-amber-900 ring-amber-200', iconoClase: 'text-amber-600' },
  error: { icono: XCircle, clase: 'bg-red-50 text-red-800 ring-red-200', iconoClase: 'text-red-600' },
  info: { icono: Info, clase: 'bg-slate-50 text-slate-700 ring-slate-200', iconoClase: 'text-slate-500' },
};

export default function Aviso({ tono = 'info', titulo, children, accion, className = '' }) {
  const { icono: Icono, clase, iconoClase } = TONOS[tono];
  return (
    <div role={tono === 'error' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-xl p-3.5 text-sm ring-1 ${clase} ${className}`}>
      <Icono className={`mt-0.5 h-4 w-4 shrink-0 ${iconoClase}`} />
      <div className="min-w-0 flex-1">
        {titulo && <p className="font-semibold">{titulo}</p>}
        {children && <div className={titulo ? 'mt-0.5' : ''}>{children}</div>}
      </div>
      {accion}
    </div>
  );
}
