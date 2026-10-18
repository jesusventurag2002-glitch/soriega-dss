import { ESTADOS, ESTADO_DESCONOCIDO } from './traslados/estados.js';

const ABC = {
  A: { clase: 'bg-emerald-600 text-white', titulo: 'Clase A · Alta rotación' },
  B: { clase: 'bg-sky-600 text-white', titulo: 'Clase B · Rotación media' },
  C: { clase: 'bg-slate-300 text-slate-700', titulo: 'Clase C · Baja rotación' },
};

const SIN_CLASIFICAR = { clase: 'bg-slate-100 text-slate-400', titulo: 'Sin clasificación ABC' };

export function AbcBadge({ clase }) {
  const { clase: estilos, titulo } = ABC[clase] ?? SIN_CLASIFICAR;
  return (
    <span
      title={titulo}
      className={`inline-flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold ${estilos}`}
    >
      {ABC[clase] ? clase : '–'}
    </span>
  );
}

// Estado de un traslado: icono + texto + color, para no depender solo del color.
export function EstadoBadge({ estado }) {
  const { texto, icono: Icono, clase } = ESTADOS[estado] ?? ESTADO_DESCONOCIDO;
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${clase}`}>
      <Icono className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {texto}
    </span>
  );
}
