import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { ArrowRight, TrendingUp } from 'lucide-react';
import { VENTAS_SUCURSALES, VENTAS_ULTIMOS_7_DIAS } from '../data/mockData.js';
import { usd } from '../utils/formato.js';

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
  const totalMes = VENTAS_SUCURSALES.reduce((s, x) => s + x.total, 0);
  const total7Dias = VENTAS_ULTIMOS_7_DIAS.reduce((s, d) => s + d.total, 0);
  const mes = new Date().toLocaleDateString('es-VE', { month: 'long', year: 'numeric' });
  const mesCapitalizado = mes.charAt(0).toUpperCase() + mes.slice(1);

  return (
    <section className="rounded-xl bg-white p-4 sm:p-5 ring-1 ring-slate-200">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="sm:w-64 shrink-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-slate-600">Ventas del mes</p>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Demo
            </span>
          </div>
          <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">{usd(totalMes, 0)}</p>
          <p className="mt-0.5 text-xs text-slate-500">{mesCapitalizado} · {VENTAS_SUCURSALES.length} sucursales</p>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="inline-flex items-center gap-1">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-600" /> Últimos 7 días
            </span>
            <span className="font-medium text-slate-700">{usd(total7Dias, 0)}</span>
          </div>
          <div className="mt-1 h-16">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={VENTAS_ULTIMOS_7_DIAS} margin={{ top: 6, right: 6, bottom: 2, left: 6 }}>
                <defs>
                  <linearGradient id="relleno-ventas" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={AZUL} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={AZUL} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis hide domain={['dataMin - 500', 'dataMax + 300']} />
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
