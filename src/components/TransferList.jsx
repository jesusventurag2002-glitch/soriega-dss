import { ArrowRight, Check, X, Inbox } from 'lucide-react';
import { AbcBadge, EstadoBadge } from './Badges.jsx';

const STOCK_CRITICO = 20;

function Ruta({ origen, destino }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-500">
      {origen} <ArrowRight className="h-3 w-3" /> {destino}
    </span>
  );
}

function StockDestino({ valor }) {
  return (
    <span className={valor < STOCK_CRITICO ? 'font-semibold text-red-600' : 'text-slate-700'}>{valor}</span>
  );
}

// Analista ajusta la cantidad; Gerente aprueba o rechaza. Solo aplica a pendientes.
function CantidadSugerida({ traslado, rol, onActualizar }) {
  if (rol !== 'analista' || traslado.estado !== 'pendiente') {
    return <span className="font-semibold text-slate-900">{traslado.cantidad_sugerida}</span>;
  }
  return (
    <input
      type="number"
      min={0}
      max={traslado.stock_origen}
      value={traslado.cantidad_sugerida}
      onChange={(e) => onActualizar(traslado.id, { cantidad_sugerida: Number(e.target.value) })}
      className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-right text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-slate-900"
    />
  );
}

function Acciones({ traslado, rol, onActualizar, compacto = false }) {
  if (rol !== 'gerente' || traslado.estado !== 'pendiente') return null;
  const base = 'inline-flex items-center justify-center gap-1 rounded-lg text-sm font-medium transition';
  const tam = compacto ? 'h-8 w-8' : 'flex-1 py-2';
  return (
    <div className={`flex gap-2 ${compacto ? '' : 'pt-3'}`}>
      <button
        title="Aprobar"
        onClick={() => onActualizar(traslado.id, { estado: 'aprobado' })}
        className={`${base} ${tam} bg-emerald-600 text-white hover:bg-emerald-700`}
      >
        <Check className="h-4 w-4" /> {!compacto && 'Aprobar'}
      </button>
      <button
        title="Rechazar"
        onClick={() => onActualizar(traslado.id, { estado: 'rechazado' })}
        className={`${base} ${tam} bg-white text-red-600 ring-1 ring-red-200 hover:bg-red-50`}
      >
        <X className="h-4 w-4" /> {!compacto && 'Rechazar'}
      </button>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-16 rounded-xl bg-slate-200/70 animate-pulse" />
      ))}
    </div>
  );
}

export default function TransferList({ traslados, cargando, rol, onActualizar }) {
  if (cargando) return <Skeleton />;

  if (traslados.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl bg-white ring-1 ring-slate-200 py-12 text-slate-400">
        <Inbox className="h-8 w-8 mb-2" />
        <p className="text-sm">No hay traslados en este estado</p>
      </div>
    );
  }

  const props = { rol, onActualizar };

  return (
    <>
      {/* Desktop: DataGrid */}
      <div className="hidden md:block overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">ABC</th>
              <th className="px-4 py-3">Producto</th>
              <th className="px-4 py-3 text-right">Stock origen</th>
              <th className="px-4 py-3 text-right">Stock destino</th>
              <th className="px-4 py-3 text-right">Sugerido</th>
              <th className="px-4 py-3">Estado</th>
              {rol === 'gerente' && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {traslados.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50 transition">
                <td className="px-4 py-3">
                  <AbcBadge clase={t.clasificacion_abc} />
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-900">{t.descripcion}</p>
                  <p className="text-xs text-slate-400 font-mono">
                    {t.id} · {t.codigo}
                  </p>
                  <Ruta origen={t.origen} destino={t.destino} />
                </td>
                <td className="px-4 py-3 text-right text-slate-700">{t.stock_origen}</td>
                <td className="px-4 py-3 text-right">
                  <StockDestino valor={t.stock_destino} />
                </td>
                <td className="px-4 py-3 text-right">
                  <CantidadSugerida traslado={t} {...props} />
                </td>
                <td className="px-4 py-3">
                  <EstadoBadge estado={t.estado} />
                </td>
                {rol === 'gerente' && (
                  <td className="px-4 py-3">
                    <Acciones traslado={t} {...props} compacto />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile: tarjetas apilables */}
      <div className="md:hidden space-y-3">
        {traslados.map((t) => (
          <article key={t.id} className="rounded-xl bg-white ring-1 ring-slate-200 p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <AbcBadge clase={t.clasificacion_abc} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900 leading-snug">{t.descripcion}</p>
                <p className="text-xs text-slate-400 font-mono truncate">{t.codigo}</p>
              </div>
              <EstadoBadge estado={t.estado} />
            </div>

            <div className="mt-2">
              <Ruta origen={t.origen} destino={t.destino} />
            </div>

            <dl className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
              <div>
                <dt className="text-[11px] text-slate-500">Origen</dt>
                <dd className="text-sm text-slate-700">{t.stock_origen}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500">Destino</dt>
                <dd className="text-sm">
                  <StockDestino valor={t.stock_destino} />
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500">Sugerido</dt>
                <dd className="text-sm">
                  <CantidadSugerida traslado={t} {...props} />
                </dd>
              </div>
            </dl>

            <Acciones traslado={t} {...props} />
          </article>
        ))}
      </div>
    </>
  );
}
