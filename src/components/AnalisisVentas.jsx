import { useState } from 'react';
import { Bar, BarChart, Cell, LabelList, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import { ArrowLeft, BarChart3, Store } from 'lucide-react';
import { VENTAS_SUCURSALES } from '../data/mockData.js';
import { usd, usdCompacto } from '../utils/formato.js';

// Color fijo por grupo (sigue a la entidad, no a su posición). Paleta validada para daltonismo
// en los pares contiguos del anillo; el aqua y el ámbar tienen poco contraste, por eso la tabla acompaña al gráfico.
const COLOR_GRUPO = {
  Hogar: '#2a78d6',
  Automotriz: '#eb6834',
  Eléctrico: '#1baf7a',
  Ferretería: '#eda100',
};

const AZUL = '#2a78d6';
const AZUL_TENUE = '#b7d3f6';
const GRID = '#e1e0d9';
const TINTA_EJE = '#898781';

const totalGeneral = VENTAS_SUCURSALES.reduce((s, x) => s + x.total, 0);

function TooltipMonto({ active, payload, total }) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0];
  return (
    <div className="rounded-lg bg-white px-2.5 py-1.5 text-xs shadow-lg ring-1 ring-slate-200">
      <p className="text-slate-500">{name}</p>
      <p className="font-semibold text-slate-900">
        {usd(value, 0)} <span className="font-normal text-slate-500">· {((value / total) * 100).toFixed(1)}%</span>
      </p>
    </div>
  );
}

function Tarjeta({ titulo, subtitulo, children }) {
  return (
    <section className="rounded-xl bg-white p-4 sm:p-5 ring-1 ring-slate-200">
      <h2 className="font-semibold text-slate-900">{titulo}</h2>
      {subtitulo && <p className="text-xs text-slate-500">{subtitulo}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function AnalisisVentas({ onVolver }) {
  const [seleccion, setSeleccion] = useState(VENTAS_SUCURSALES[0].sucursal);
  const sucursal = VENTAS_SUCURSALES.find((s) => s.sucursal === seleccion);
  const gruposOrdenados = [...sucursal.grupos].sort((a, b) => b.total - a.total);

  return (
    <div className="space-y-6">
      <div>
        <button
          onClick={onVolver}
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" /> Volver al dashboard
        </button>
        <div className="mt-2 flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-slate-900 text-white flex items-center justify-center">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold text-slate-900">Análisis de ventas</h1>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Demo
              </span>
            </div>
            <p className="text-sm text-slate-500">
              {usd(totalGeneral, 0)} este mes en {VENTAS_SUCURSALES.length} sucursales
            </p>
          </div>
        </div>
      </div>

      {/* Selector de sucursal: controla el desglose y resalta la barra correspondiente */}
      <div role="tablist" aria-label="Sucursal" className="flex gap-2 overflow-x-auto pb-1">
        {VENTAS_SUCURSALES.map((s) => (
          <button
            key={s.sucursal}
            role="tab"
            aria-selected={s.sucursal === seleccion}
            onClick={() => setSeleccion(s.sucursal)}
            className={`inline-flex items-center gap-2 whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition ${
              s.sucursal === seleccion
                ? 'bg-slate-900 text-white'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
            }`}
          >
            <Store className="h-4 w-4" /> {s.sucursal}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <Tarjeta titulo="Ventas por sucursal" subtitulo="Toca una barra para ver su desglose">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={VENTAS_SUCURSALES} margin={{ top: 20, right: 8, bottom: 0, left: 0 }} barCategoryGap="28%">
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="sucursal" tickLine={false} axisLine={{ stroke: '#c3c2b7' }} tick={{ fill: TINTA_EJE, fontSize: 12 }} />
                  <YAxis
                    tickFormatter={usdCompacto}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                    tick={{ fill: TINTA_EJE, fontSize: 11 }}
                  />
                  <Tooltip content={<TooltipMonto total={totalGeneral} />} cursor={{ fill: 'rgba(11,11,11,0.04)' }} />
                  <Bar
                    dataKey="total"
                    nameKey="sucursal"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={56}
                    isAnimationActive={false}
                    className="cursor-pointer"
                    onClick={(d) => setSeleccion(d.sucursal)}
                  >
                    {VENTAS_SUCURSALES.map((s) => (
                      <Cell key={s.sucursal} fill={s.sucursal === seleccion ? AZUL : AZUL_TENUE} />
                    ))}
                    <LabelList dataKey="total" position="top" formatter={usdCompacto} fill="#52514e" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Tarjeta>
        </div>

        <div className="lg:col-span-3">
          <Tarjeta
            titulo={`Desglose · Sucursal ${sucursal.sucursal}`}
            subtitulo={`${((sucursal.total / totalGeneral) * 100).toFixed(1)}% de las ventas del mes`}
          >
            <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-2">
              <div className="relative h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Tooltip content={<TooltipMonto total={sucursal.total} />} />
                    {/* Orden fijo de grupos: mantiene la posición de cada color entre sucursales */}
                    <Pie
                      data={sucursal.grupos}
                      dataKey="total"
                      nameKey="grupo"
                      innerRadius="62%"
                      outerRadius="92%"
                      startAngle={90}
                      endAngle={-270}
                      stroke="#ffffff"
                      strokeWidth={2}
                      isAnimationActive={false}
                    >
                      {sucursal.grupos.map((g) => (
                        <Cell key={g.grupo} fill={COLOR_GRUPO[g.grupo]} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <p className="text-xs text-slate-500">Total</p>
                  <p className="text-lg font-bold text-slate-900">{usd(sucursal.total, 0)}</p>
                </div>
              </div>

              {/* La tabla es también la leyenda del anillo */}
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th className="pb-2">Grupo</th>
                    <th className="pb-2 text-right">Ventas</th>
                    <th className="pb-2 text-right">Aporte</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 tabular-nums">
                  {gruposOrdenados.map((g) => (
                    <tr key={g.grupo}>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-2 text-slate-700">
                          <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: COLOR_GRUPO[g.grupo] }} />
                          {g.grupo}
                        </span>
                      </td>
                      <td className="py-2 text-right font-medium text-slate-900">{usd(g.total, 0)}</td>
                      <td className="py-2 text-right text-slate-500">{((g.total / sucursal.total) * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Tarjeta>
        </div>
      </div>
    </div>
  );
}
