import { useEffect, useState } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { ArrowRight, TrendingUp, XCircle } from 'lucide-react';
import { obtenerAnalisisVentas } from '../services/api.js';
import { fechaLocal, nombreMes, usd } from '../utils/formato.js';

const AZUL = '#2a78d6';

const dia = (fecha) => fecha.toLocaleDateString('es-VE', { weekday: 'short', day: 'numeric', month: 'short' });

function TooltipDia({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { fecha, total } = payload[0].payload;
  return (
    <div className="rounded-lg bg-white px-2.5 py-1.5 text-xs shadow-lg ring-1 ring-slate-200">
      <p className="text-slate-500 capitalize">{dia(fecha)}</p>
      <p className="font-semibold text-slate-900">{usd(total, 0)}</p>
    </div>
  );
}

export default function WidgetVentas({ onVerDesglose }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    obtenerAnalisisVentas()
      .then(setDatos)
      .catch((e) => setError(e instanceof TypeError ? 'No se pudo conectar con el servidor.' : e.message));
  }, []);

  const serie = datos?.ultimos_7_dias.map((d) => ({ ...d, fecha: fechaLocal(d.fecha) })) ?? [];
  const total7Dias = serie.reduce((s, d) => s + d.total, 0);
  const corte = datos && fechaLocal(datos.fecha_corte);

  return (
    <section className="rounded-xl bg-white p-4 sm:p-5 ring-1 ring-slate-200">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="sm:w-64 shrink-0">
          <p className="text-sm font-medium text-slate-600">
            Ventas del mes <span className="font-normal text-slate-400">· sin excepciones</span>
          </p>
          {error ? (
            <p className="mt-2 flex items-start gap-1.5 text-sm text-red-700">
              <XCircle className="h-4 w-4 shrink-0 mt-0.5" /> {error}
            </p>
          ) : datos ? (
            <>
              <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">{usd(datos.total_mes, 0)}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {nombreMes(datos.mes, datos.ano)} · al {corte.toLocaleDateString('es-VE')} · {datos.sucursales.length}{' '}
                {datos.sucursales.length === 1 ? 'sucursal' : 'sucursales'}
              </p>
            </>
          ) : (
            <div className="mt-2 space-y-2">
              <div className="h-8 w-40 rounded bg-slate-200/70 animate-pulse" />
              <div className="h-3 w-32 rounded bg-slate-200/70 animate-pulse" />
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="inline-flex items-center gap-1">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-600" /> Últimos 7 días
            </span>
            {datos && <span className="font-medium text-slate-700">{usd(total7Dias, 0)}</span>}
          </div>
          <div className="mt-1 h-16">
            {datos && (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={serie} margin={{ top: 6, right: 6, bottom: 2, left: 6 }}>
                  <defs>
                    <linearGradient id="relleno-ventas" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={AZUL} stopOpacity={0.22} />
                      <stop offset="100%" stopColor={AZUL} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={[0, 'dataMax']} />
                  <Tooltip content={<TooltipDia />} cursor={{ stroke: '#c3c2b7', strokeWidth: 1 }} />
                  <Area
                    type="monotone"
                    dataKey="total"
                    stroke={AZUL}
                    strokeWidth={2}
                    fill="url(#relleno-ventas)"
                    dot={false}
                    isAnimationActive={false}
                    activeDot={{ r: 4, fill: AZUL, stroke: '#fff', strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <button
          onClick={onVerDesglose}
          className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          Ver desglose <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </section>
  );
}
