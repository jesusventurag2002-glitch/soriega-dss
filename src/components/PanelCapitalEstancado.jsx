import { useMemo, useState } from 'react';
import { AlertOctagon, DollarSign, PackageX, Hourglass, Tag, Warehouse, Truck, TrendingDown } from 'lucide-react';

// Datos simulados: artículos de alto costo sin rotación que distorsionan la clasificación ABC.
const conCapital = (p) => ({ ...p, capital_estancado: p.existencia * p.costo_unitario });

const INACTIVOS_MOCK = [
  { codigo: '4410021', descripcion: 'Motosierra Industrial 24"', existencia: 6, costo_unitario: 385.5, dias_sin_vender: 365 },
  { codigo: '4420107', descripcion: 'Generador Eléctrico 5500W', existencia: 3, costo_unitario: 690.0, dias_sin_vender: 298 },
  { codigo: '4430318', descripcion: 'Soldadora Inverter 250A', existencia: 8, costo_unitario: 172.4, dias_sin_vender: 210 },
  { codigo: '4400562', descripcion: 'Compresor de Aire 50L', existencia: 5, costo_unitario: 214.9, dias_sin_vender: 180 },
  { codigo: '4450893', descripcion: 'Hidrolavadora Profesional 2000PSI', existencia: 4, costo_unitario: 158.75, dias_sin_vender: 145 },
  { codigo: '4460014', descripcion: 'Taladro Percutor Inalámbrico 20V', existencia: 12, costo_unitario: 64.3, dias_sin_vender: 120 },
].map(conCapital);

const ACCIONES = [
  { id: 'promocion', texto: 'Sugerir descuento / promoción', corto: 'Promoción', icono: Tag, estilo: 'text-amber-700 ring-amber-200 hover:bg-amber-50' },
  { id: 'retorno', texto: 'Retornar a Almacén Principal', corto: 'Al almacén', icono: Warehouse, estilo: 'text-slate-700 ring-slate-300 hover:bg-slate-100' },
  { id: 'devolucion', texto: 'Devolución a proveedor', corto: 'A proveedor', icono: Truck, estilo: 'text-red-700 ring-red-200 hover:bg-red-50' },
];

const usd = (n) => `$${n.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const severidad = (dias) =>
  dias >= 365
    ? { texto: 'Crítico', clase: 'bg-red-600 text-white' }
    : dias >= 180
      ? { texto: 'Alto', clase: 'bg-amber-500 text-white' }
      : { texto: 'Moderado', clase: 'bg-amber-100 text-amber-800' };

function Kpi({ icono: Icono, etiqueta, valor, detalle, tono }) {
  const tonos = {
    rojo: 'bg-red-600 text-white ring-red-700',
    ambar: 'bg-amber-50 text-amber-900 ring-amber-200',
    neutro: 'bg-white text-slate-900 ring-slate-200',
  };
  return (
    <div className={`rounded-xl p-4 ring-1 ${tonos[tono]}`}>
      <div className="flex items-center gap-2 text-sm font-medium opacity-90">
        <Icono className="h-4 w-4" /> {etiqueta}
      </div>
      <p className="mt-2 text-2xl sm:text-3xl font-bold tracking-tight">{valor}</p>
      {detalle && <p className="mt-1 text-xs opacity-80">{detalle}</p>}
    </div>
  );
}

function DiasSinVender({ dias }) {
  const { texto, clase } = severidad(dias);
  return (
    <div className="flex items-center gap-2">
      <span className="font-semibold text-slate-900">{dias} d</span>
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${clase}`}>{texto}</span>
    </div>
  );
}

// Barra con el peso del artículo sobre el capital inmovilizado total.
function ParticipacionCapital({ capital, total }) {
  const pct = total ? (capital / total) * 100 : 0;
  return (
    <div>
      <p className="font-semibold text-red-700">{usd(capital)}</p>
      <div className="mt-1 flex items-center gap-2">
        <div className="h-1.5 w-24 rounded-full bg-slate-200 overflow-hidden">
          <div className="h-full rounded-full bg-red-500" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] text-slate-500">{pct.toFixed(1)}%</span>
      </div>
    </div>
  );
}

function Acciones({ articulo, onAccion, compacto = false }) {
  return (
    <div className={compacto ? 'flex gap-1.5' : 'grid grid-cols-1 gap-2 sm:grid-cols-3'}>
      {ACCIONES.map((a) => {
        const Icono = a.icono;
        return (
          <button
            key={a.id}
            title={a.texto}
            onClick={() => onAccion(a, articulo)}
            className={`inline-flex items-center justify-center gap-1.5 rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium ring-1 transition ${a.estilo}`}
          >
            <Icono className="h-3.5 w-3.5 shrink-0" />
            {compacto ? a.corto : a.texto}
          </button>
        );
      })}
    </div>
  );
}

export default function PanelCapitalEstancado() {
  const [articulos] = useState(INACTIVOS_MOCK);

  const ordenados = useMemo(
    () => [...articulos].sort((a, b) => b.capital_estancado - a.capital_estancado),
    [articulos]
  );
  const capitalTotal = useMemo(() => articulos.reduce((s, a) => s + a.capital_estancado, 0), [articulos]);
  const promedioDias = articulos.length
    ? Math.round(articulos.reduce((s, a) => s + a.dias_sin_vender, 0) / articulos.length)
    : 0;
  const criticos = articulos.filter((a) => a.dias_sin_vender >= 365).length;

  const ejecutarAccion = (accion, articulo) => {
    console.log('Acción estratégica', { accion: accion.id, codigo: articulo.codigo, capital: articulo.capital_estancado });
    alert(`${accion.texto}\n\n${articulo.descripcion} (${articulo.codigo})\nCapital comprometido: ${usd(articulo.capital_estancado)}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-red-600 text-white flex items-center justify-center shadow-sm">
          <AlertOctagon className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Capital estancado</h1>
          <p className="text-sm text-slate-500">Artículos inactivos que inmovilizan capital y requieren una decisión</p>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-xl border-l-4 border-red-600 bg-red-50 p-4 ring-1 ring-red-200">
        <TrendingDown className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
        <p className="text-sm text-red-900">
          <span className="font-semibold">Atención requerida.</span> Estos artículos se excluyen de la clasificación ABC para
          no ocultar a los de alta rotación. Cada día sin decisión mantiene{' '}
          <span className="font-semibold">{usd(capitalTotal)}</span> fuera del flujo de caja.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icono={DollarSign} etiqueta="Capital inmovilizado total" valor={usd(capitalTotal)} tono="rojo" detalle="Existencia × costo unitario" />
        <Kpi icono={PackageX} etiqueta="Artículos inactivos" valor={articulos.length} tono="ambar" detalle={`${criticos} con un año o más sin ventas`} />
        <Kpi icono={Hourglass} etiqueta="Promedio sin vender" valor={`${promedioDias} días`} tono="ambar" />
        <Kpi
          icono={AlertOctagon}
          etiqueta="Mayor exposición"
          valor={ordenados[0] ? usd(ordenados[0].capital_estancado) : '—'}
          tono="neutro"
          detalle={ordenados[0]?.descripcion}
        />
      </div>

      {/* Escritorio (lg+): tabla ordenada por capital estancado */}
      <div className="hidden lg:block overflow-x-auto rounded-xl bg-white ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">#</th>
              <th className="px-4 py-3">Artículo</th>
              <th className="px-4 py-3 text-right">Existencia</th>
              <th className="px-4 py-3 text-right">Costo unit.</th>
              <th className="px-4 py-3">Sin vender</th>
              <th className="px-4 py-3">Capital estancado ↓</th>
              <th className="px-4 py-3">Decisión</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {ordenados.map((a, i) => (
              <tr key={a.codigo} className="hover:bg-red-50/40 transition">
                <td className="px-4 py-3 text-slate-400 font-medium">{i + 1}</td>
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-900">{a.descripcion}</p>
                  <p className="text-xs text-slate-400 font-mono">{a.codigo}</p>
                </td>
                <td className="px-4 py-3 text-right text-slate-700">{a.existencia}</td>
                <td className="px-4 py-3 text-right text-slate-700">{usd(a.costo_unitario)}</td>
                <td className="px-4 py-3">
                  <DiasSinVender dias={a.dias_sin_vender} />
                </td>
                <td className="px-4 py-3">
                  <ParticipacionCapital capital={a.capital_estancado} total={capitalTotal} />
                </td>
                <td className="px-4 py-3">
                  <Acciones articulo={a} onAccion={ejecutarAccion} compacto />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Móvil y tablet: tarjetas apilables */}
      <div className="lg:hidden space-y-3">
        {ordenados.map((a, i) => (
          <article key={a.codigo} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 border-l-4 border-red-500">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium text-slate-400">
                  #{i + 1} · <span className="font-mono">{a.codigo}</span>
                </p>
                <p className="font-medium text-slate-900 leading-snug">{a.descripcion}</p>
              </div>
              <DiasSinVender dias={a.dias_sin_vender} />
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3">
              <div>
                <dt className="text-[11px] text-slate-500">Existencia</dt>
                <dd className="text-sm text-slate-700">{a.existencia} × {usd(a.costo_unitario)}</dd>
              </div>
              <div>
                <dt className="text-[11px] text-slate-500">Capital estancado</dt>
                <dd className="text-sm">
                  <ParticipacionCapital capital={a.capital_estancado} total={capitalTotal} />
                </dd>
              </div>
            </dl>

            <div className="mt-3">
              <Acciones articulo={a} onAccion={ejecutarAccion} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
