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

const ESTADOS = {
  pendiente: { texto: 'Pendiente', clase: 'bg-amber-50 text-amber-700 ring-amber-200', punto: 'bg-amber-500' },
  aprobado: { texto: 'Aprobado', clase: 'bg-emerald-50 text-emerald-700 ring-emerald-200', punto: 'bg-emerald-500' },
  rechazado: { texto: 'Rechazado', clase: 'bg-red-50 text-red-700 ring-red-200', punto: 'bg-red-500' },
};

export function EstadoBadge({ estado }) {
  const { texto, clase, punto } = ESTADOS[estado] ?? { texto: estado, clase: 'bg-slate-50 text-slate-600 ring-slate-200', punto: 'bg-slate-400' };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${clase}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${punto}`} />
      {texto}
    </span>
  );
}
