import { useCallback, useEffect, useState } from 'react';
import { Bar, BarChart, Cell, LabelList, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import { ArrowLeft, BarChart3, Store, XCircle, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { guardarExcepciones, obtenerAnalisisVentas } from '../services/api.js';
import AdministrarExcepciones from './AdministrarExcepciones.jsx';
import { capitalizar, fechaLocal, nombreMes, usd, usdCompacto } from '../utils/formato.js';

// Colores en orden fijo para los grupos principales del mes (validados para daltonismo en los pares
// contiguos del anillo) y gris neutro para "Otros". El color sigue al grupo en todas las sucursales.
// Tres tonos tienen poco contraste sobre blanco, por eso la tabla acompaña al gráfico.
const PALETA_GRUPOS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
const GRIS_OTROS = '#c3c2b7';

const AZUL = '#2a78d6';
const AZUL_TENUE = '#b7d3f6';
const GRID = '#e1e0d9';
const TINTA_EJE = '#898781';

const etiquetaGrupo = (g) => (g === 'OTROS' ? 'Otros grupos' : capitalizar(g));

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

function ComparativoSucursales({ sucursales, seleccion, onSeleccionar, totalMes }) {
  // Con una sola sucursal un gráfico de una barra no aporta: se muestra la cifra.
  if (sucursales.length === 1) {
    return (
      <Tarjeta titulo="Ventas por sucursal">
        <p className="text-sm text-slate-500">{sucursales[0].sucursal}</p>
        <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900">{usd(sucursales[0].total, 0)}</p>
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
          Solo hay ventas cargadas de una sucursal. Sube el historial de ventas de las demás en Configuración inicial
          para compararlas aquí.
        </p>
      </Tarjeta>
    );
  }
  return (
    <Tarjeta titulo="Ventas por sucursal" subtitulo="Toca una barra para ver su desglose">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={sucursales} margin={{ top: 20, right: 8, bottom: 0, left: 0 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="sucursal" tickLine={false} axisLine={{ stroke: '#c3c2b7' }} tick={{ fill: TINTA_EJE, fontSize: 12 }} />
            <YAxis tickFormatter={usdCompacto} tickLine={false} axisLine={false} width={48} tick={{ fill: TINTA_EJE, fontSize: 11 }} />
            <Tooltip content={<TooltipMonto total={totalMes} />} cursor={{ fill: 'rgba(11,11,11,0.04)' }} />
            <Bar
              dataKey="total"
              nameKey="sucursal"
              radius={[4, 4, 0, 0]}
              maxBarSize={56}
              isAnimationActive={false}
              className="cursor-pointer"
              onClick={(d) => onSeleccionar(d.sucursal)}
            >
              {sucursales.map((s) => (
                <Cell key={s.sucursal} fill={s.sucursal === seleccion ? AZUL : AZUL_TENUE} />
              ))}
              <LabelList dataKey="total" position="top" formatter={usdCompacto} fill="#52514e" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Tarjeta>
  );
}

export default function AnalisisVentas({ onVolver }) {
  const [datos, setDatos] = useState(null);
  const [periodo, setPeriodo] = useState(null); // null = mes de la última venta registrada
  const [menuExcepciones, setMenuExcepciones] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [seleccion, setSeleccion] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const d = await obtenerAnalisisVentas(periodo);
      setDatos(d);
      setSeleccion((actual) => (d.sucursales.some((s) => s.sucursal === actual) ? actual : d.sucursales[0]?.sucursal ?? null));
    } catch (e) {
      setError(
        e instanceof TypeError
          ? 'No se pudo conectar con el servidor. Verifica que el backend esté activo en el puerto 5000.'
          : e.message
      );
    } finally {
      setCargando(false);
    }
  }, [periodo]);

  // Guarda la selección en el backend (null = restablecer) y recalcula con ella.
  const cambiarExcepciones = async (excluir) => {
    setGuardando(true);
    try {
      await guardarExcepciones(excluir);
      await cargar();
    } catch (e) {
      setError(e instanceof TypeError ? 'No se pudo conectar con el servidor.' : e.message);
      setMenuExcepciones(false);
    } finally {
      setGuardando(false);
    }
  };

  useEffect(() => {
    cargar();
  }, [cargar]);

  const colorGrupo = (g) => (g === 'OTROS' ? GRIS_OTROS : PALETA_GRUPOS[datos.grupos_principales.indexOf(g)]);
  const sucursal = datos?.sucursales.find((s) => s.sucursal === seleccion);
  const gruposOrdenados = sucursal ? [...sucursal.grupos].sort((a, b) => b.total - a.total) : [];

  return (
    <div className="space-y-6">
      <div>
        <button
          onClick={onVolver}
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" /> Volver al dashboard
        </button>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 rounded-xl bg-slate-900 text-white flex items-center justify-center">
              <BarChart3 className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Análisis de ventas</h1>
              <p className="text-sm text-slate-500">
                {datos
                  ? `${usd(datos.total_mes, 0)} en ${nombreMes(datos.mes, datos.ano)} · ${datos.sucursales.length} ${
                      datos.sucursales.length === 1 ? 'sucursal' : 'sucursales'
                    } · datos al ${fechaLocal(datos.fecha_corte).toLocaleDateString('es-VE')}`
                  : 'Facturación real en USD por sucursal y grupo de producto'}
              </p>
            </div>
          </div>
          {datos && (
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="periodo" className="text-sm text-slate-500">
                Mes
              </label>
              <select
                id="periodo"
                value={`${datos.ano}-${datos.mes}`}
                onChange={(e) => {
                  const [ano, mes] = e.target.value.split('-').map(Number);
                  setPeriodo({ mes, ano });
                }}
                disabled={cargando}
                className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
              >
                {datos.meses_disponibles.map(({ mes, ano }) => (
                  <option key={`${ano}-${mes}`} value={`${ano}-${mes}`}>
                    {nombreMes(mes, ano)}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setMenuExcepciones(true)}
                title="Administrar excepciones"
                className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100"
              >
                <SlidersHorizontal className="h-4 w-4" />
                <span className="hidden sm:inline">Excepciones</span>
                <span className="rounded-full bg-slate-100 px-1.5 text-xs text-slate-500">
                  {datos.excepciones.filter((e) => e.excluida).length}
                </span>
              </button>
              {cargando && <RefreshCw className="h-4 w-4 animate-spin text-slate-400" />}
            </div>
          )}
        </div>
      </div>

      {menuExcepciones && datos && (
        <AdministrarExcepciones
          datos={{ ...datos, mesNombre: nombreMes(datos.mes, datos.ano) }}
          guardando={guardando}
          onCambiar={cambiarExcepciones}
          onCerrar={() => setMenuExcepciones(false)}
        />
      )}

      {error && (
        <div role="alert" className="flex items-start gap-3 rounded-xl bg-red-50 p-4 text-red-800 ring-1 ring-red-200">
          <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <p className="flex-1 text-sm">{error}</p>
          <button onClick={cargar} className="text-sm font-medium underline underline-offset-2">
            Reintentar
          </button>
        </div>
      )}

      {!datos && !error && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <div className="h-80 rounded-xl bg-slate-200/70 animate-pulse lg:col-span-2" />
          <div className="h-80 rounded-xl bg-slate-200/70 animate-pulse lg:col-span-3" />
        </div>
      )}

      {datos && !error && (
        // Al recargar se conserva el render anterior atenuado, sin saltos de layout.
        <div className={`space-y-6 transition-opacity ${cargando ? 'opacity-50' : ''}`}>
          {datos.dias_sin_tasa_interna > 0 && (
            <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
              {datos.dias_sin_tasa_interna} {datos.dias_sin_tasa_interna === 1 ? 'día' : 'días'} de este mes sin tasa
              interna cargada: sus ventas se convirtieron con la tasa BCV del sistema. Carga la hoja TASA en
              Configuración inicial.
            </p>
          )}

          {datos.sucursales.length > 1 && (
            <div role="tablist" aria-label="Sucursal" className="flex gap-2 overflow-x-auto pb-1">
              {datos.sucursales.map((s) => (
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
          )}

          {!sucursal ? (
            <div className="rounded-xl bg-white py-12 text-center text-sm text-slate-400 ring-1 ring-slate-200">
              No hay ventas registradas en {nombreMes(datos.mes, datos.ano)}.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
              <div className="lg:col-span-2">
                <ComparativoSucursales
                  sucursales={datos.sucursales}
                  seleccion={seleccion}
                  onSeleccionar={setSeleccion}
                  totalMes={datos.total_mes}
                />
              </div>

              <div className="lg:col-span-3">
                <Tarjeta
                  titulo={`Desglose · Sucursal ${sucursal.sucursal}`}
                  subtitulo={
                    datos.sucursales.length > 1
                      ? `${((sucursal.total / datos.total_mes) * 100).toFixed(1)}% de las ventas del mes`
                      : `Principales grupos de producto en ${nombreMes(datos.mes, datos.ano)}`
                  }
                >
                  <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-2">
                    <div className="relative h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Tooltip content={<TooltipMonto total={sucursal.total} />} />
                          {/* Orden fijo de grupos: mantiene la posición de cada color entre sucursales */}
                          <Pie
                            data={sucursal.grupos
                              .filter((g) => g.total > 0)
                              .map((g) => ({ ...g, nombre: etiquetaGrupo(g.grupo) }))}
                            dataKey="total"
                            nameKey="nombre"
                            innerRadius="62%"
                            outerRadius="92%"
                            startAngle={90}
                            endAngle={-270}
                            stroke="#ffffff"
                            strokeWidth={2}
                            isAnimationActive={false}
                          >
                            {sucursal.grupos
                              .filter((g) => g.total > 0)
                              .map((g) => (
                                <Cell key={g.grupo} fill={colorGrupo(g.grupo)} />
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
                                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: colorGrupo(g.grupo) }} />
                                {etiquetaGrupo(g.grupo)}
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
          )}
        </div>
      )}
    </div>
  );
}
