import { useCallback, useEffect, useState } from 'react';
import {
  AlertOctagon, DollarSign, PackageX, Hourglass, Tag, Warehouse, Truck, TrendingDown, RefreshCw, XCircle,
} from 'lucide-react';
import { obtenerCapitalEstancado } from '../services/api.js';

const UMBRALES = [60, 90, 180];

const ACCIONES = [
  { id: 'promocion', texto: 'Sugerir descuento / promoción', corto: 'Promoción', icono: Tag, estilo: 'text-amber-700 ring-amber-200 hover:bg-amber-50' },
  { id: 'retorno', texto: 'Retornar a Almacén Principal', corto: 'Al almacén', icono: Warehouse, estilo: 'text-slate-700 ring-slate-300 hover:bg-slate-100' },
  { id: 'devolucion', texto: 'Devolución a proveedor', corto: 'A proveedor', icono: Truck, estilo: 'text-red-700 ring-red-200 hover:bg-red-50' },
];

const usd = (n) => `$${n.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fecha = (iso) => iso.split('-').reverse().join('/');

// El historial cubre menos de un año, así que "crítico" = sin ninguna venta registrada.
const severidad = (a) =>
  a.sin_ventas
    ? { texto: 'Sin ventas', clase: 'bg-red-600 text-white' }
    : a.dias_sin_vender >= 180
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
      <p className="mt-2 text-2xl sm:text-3xl font-bold tracking-tight truncate">{valor}</p>
      {detalle && <p className="mt-1 text-xs opacity-80 truncate">{detalle}</p>}
    </div>
  );
}

function DiasSinVender({ articulo }) {
  const { texto, clase } = severidad(articulo);
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="font-semibold text-slate-900">
        {articulo.sin_ventas ? '+' : ''}
        {articulo.dias_sin_vender} d
      </span>
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${clase}`}>{texto}</span>
    </div>
  );
}

function Ubicacion({ articulo }) {
  return (
    <span className="text-xs text-slate-500 whitespace-nowrap">
      Suc. {articulo.existencia_sucursal} · Alm. {articulo.existencia_almacen}
    </span>
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
          <div className="h-full rounded-full bg-red-500" style={{ width: `${Math.max(pct, 1)}%` }} />
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
        // Solo se puede retornar al almacén lo que está en la sucursal.
        const deshabilitado = a.id === 'retorno' && articulo.existencia_sucursal === 0;
        return (
          <button
            key={a.id}
            title={deshabilitado ? 'Sin existencia en la sucursal' : a.texto}
            disabled={deshabilitado}
            onClick={() => onAccion(a, articulo)}
            className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium ring-1 transition disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white ${a.estilo}`}
          >
            <Icono className="h-3.5 w-3.5 shrink-0" />
            {compacto ? a.corto : a.texto}
          </button>
        );
      })}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-16 rounded-xl bg-slate-200/70 animate-pulse" />
      ))}
    </div>
  );
}

export default function PanelCapitalEstancado() {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [diasMin, setDiasMin] = useState(90);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setDatos(await obtenerCapitalEstancado(diasMin));
    } catch (e) {
      setError(
        e instanceof TypeError
          ? 'No se pudo conectar con el servidor. Verifica que el backend esté activo en el puerto 5000.'
          : e.message
      );
    } finally {
      setCargando(false);
    }
  }, [diasMin]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const ejecutarAccion = (accion, articulo) => {
    console.log('Acción estratégica', { accion: accion.id, codigo: articulo.codigo, capital: articulo.capital_estancado });
    alert(`${accion.texto}\n\n${articulo.descripcion} (${articulo.codigo})\nCapital comprometido: ${usd(articulo.capital_estancado)}`);
  };

  const resumen = datos?.resumen;
  const articulos = datos?.articulos ?? [];
  const mayor = articulos[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-red-600 text-white flex items-center justify-center shadow-sm">
            <AlertOctagon className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Capital estancado</h1>
            <p className="text-sm text-slate-500">
              Artículos inactivos que inmovilizan capital y requieren una decisión
              {datos && ` · Corte al ${fecha(datos.fecha_corte)}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="umbral" className="text-sm text-slate-500">
            Sin ventas hace
          </label>
          <select
            id="umbral"
            value={diasMin}
            onChange={(e) => setDiasMin(Number(e.target.value))}
            disabled={cargando}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            {UMBRALES.map((d) => (
              <option key={d} value={d}>
                {d}+ días
              </option>
            ))}
          </select>
          <button
            onClick={cargar}
            disabled={cargando}
            title="Recalcular"
            className="p-2 rounded-lg text-slate-500 ring-1 ring-slate-200 bg-white hover:bg-slate-100 hover:text-slate-900 transition disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${cargando ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error ? (
        <div role="alert" className="flex items-start gap-3 rounded-xl bg-red-50 p-4 text-red-800 ring-1 ring-red-200">
          <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <p className="flex-1 text-sm">{error}</p>
          <button onClick={cargar} className="text-sm font-medium underline underline-offset-2">
            Reintentar
          </button>
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded-xl border-l-4 border-red-600 bg-red-50 p-4 ring-1 ring-red-200">
          <TrendingDown className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
          <p className="text-sm text-red-900">
            <span className="font-semibold">Atención requerida.</span> Estos artículos se separan de la clasificación ABC
            para no ocultar a los de alta rotación.{' '}
            {resumen && (
              <>
                Cada día sin decisión mantiene <span className="font-semibold">{usd(resumen.capital_total)}</span> fuera
                del flujo de caja.
              </>
            )}
          </p>
        </div>
      )}

      {cargando || !resumen ? (
        !error && <Skeleton />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi icono={DollarSign} etiqueta="Capital inmovilizado total" valor={usd(resumen.capital_total)} tono="rojo" detalle="Existencia × costo unitario" />
            <Kpi
              icono={PackageX}
              etiqueta="Artículos inactivos"
              valor={resumen.articulos.toLocaleString('es-VE')}
              tono="ambar"
              detalle={`${resumen.sin_ventas.toLocaleString('es-VE')} sin ventas en ${datos.dias_historial} días de historial`}
            />
            <Kpi icono={Hourglass} etiqueta="Promedio sin vender" valor={`${resumen.promedio_dias} días`} tono="ambar" />
            <Kpi
              icono={AlertOctagon}
              etiqueta="Mayor exposición"
              valor={mayor ? usd(mayor.capital_estancado) : '—'}
              tono="neutro"
              detalle={mayor?.descripcion}
            />
          </div>

          {articulos.length === 0 ? (
            <div className="rounded-xl bg-white py-12 text-center text-sm text-slate-400 ring-1 ring-slate-200">
              No hay artículos con más de {diasMin} días sin ventas.
            </div>
          ) : (
            <>
              {articulos.length < resumen.articulos && (
                <p className="text-xs text-slate-500">
                  Mostrando los {articulos.length} artículos con mayor capital de {resumen.articulos.toLocaleString('es-VE')}.
                </p>
              )}

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
                    {articulos.map((a, i) => (
                      <tr key={a.codigo} className="hover:bg-red-50/40 transition">
                        <td className="px-4 py-3 text-slate-400 font-medium">{i + 1}</td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900">{a.descripcion}</p>
                          <p className="text-xs text-slate-400">
                            <span className="font-mono">{a.codigo}</span> · {a.grupo}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <p className="text-slate-700">{a.existencia}</p>
                          <Ubicacion articulo={a} />
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700">{usd(a.costo_unitario)}</td>
                        <td className="px-4 py-3">
                          <DiasSinVender articulo={a} />
                        </td>
                        <td className="px-4 py-3">
                          <ParticipacionCapital capital={a.capital_estancado} total={resumen.capital_total} />
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
                {articulos.map((a, i) => (
                  <article key={a.codigo} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 border-l-4 border-red-500">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-400">
                          #{i + 1} · <span className="font-mono">{a.codigo}</span> · {a.grupo}
                        </p>
                        <p className="font-medium text-slate-900 leading-snug">{a.descripcion}</p>
                      </div>
                      <DiasSinVender articulo={a} />
                    </div>

                    <dl className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3">
                      <div>
                        <dt className="text-[11px] text-slate-500">Existencia</dt>
                        <dd className="text-sm text-slate-700">
                          {a.existencia} × {usd(a.costo_unitario)}
                        </dd>
                        <dd>
                          <Ubicacion articulo={a} />
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[11px] text-slate-500">Capital estancado</dt>
                        <dd className="text-sm">
                          <ParticipacionCapital capital={a.capital_estancado} total={resumen.capital_total} />
                        </dd>
                      </div>
                    </dl>

                    <div className="mt-3">
                      <Acciones articulo={a} onAccion={ejecutarAccion} />
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
