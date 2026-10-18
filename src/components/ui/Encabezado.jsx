// Encabezado común de pantalla: icono, título, subtítulo breve y acciones a la derecha.
export default function Encabezado({ icono: Icono, tono = 'bg-slate-900', titulo, subtitulo, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3">
        {Icono && (
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white ${tono}`}>
            <Icono className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-slate-900">{titulo}</h1>
          {subtitulo && <p className="text-sm text-slate-500">{subtitulo}</p>}
        </div>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function EstadoVacio({ icono: Icono, titulo, children }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl bg-white px-6 py-12 text-center ring-1 ring-slate-200">
      {Icono && <Icono className="mb-2 h-8 w-8 text-slate-300" />}
      <p className="font-medium text-slate-700">{titulo}</p>
      {children && <div className="mt-1 max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  );
}
