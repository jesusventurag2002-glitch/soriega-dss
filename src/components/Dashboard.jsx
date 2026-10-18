import { useCallback, useEffect, useState } from 'react';
import { Sparkles, Clock, CheckCircle2, Flame, RefreshCw, XCircle } from 'lucide-react';
import TransferList from './TransferList.jsx';
import WidgetVentas from './WidgetVentas.jsx';
import { obtenerTrasladosSugeridos } from '../services/api.js';

const FILTROS = [
  { id: 'todos', texto: 'Todos' },
  { id: 'pendiente', texto: 'Pendientes' },
  { id: 'aprobado', texto: 'Aprobados' },
  { id: 'rechazado', texto: 'Rechazados' },
];

const HORIZONTES = [7, 15, 30];

function Kpi({ icono: Icono, etiqueta, valor, acento }) {
  return (
    <div className="bg-white rounded-xl ring-1 ring-slate-200 p-4 flex items-center gap-4">
      <div className={`h-11 w-11 rounded-xl flex items-center justify-center ${acento}`}>
        <Icono className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-semibold text-slate-900">{valor}</p>
        <p className="text-xs text-slate-500">{etiqueta}</p>
      </div>
    </div>
  );
}

export default function Dashboard({ usuario, onVerVentas }) {
  const [traslados, setTraslados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [filtro, setFiltro] = useState('todos');
  const [dias, setDias] = useState(15);
  const [sucursal, setSucursal] = useState('todas');

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setTraslados(await obtenerTrasladosSugeridos(dias));
    } catch (e) {
      setError(
        e instanceof TypeError
          ? 'No se pudo conectar con el servidor. Verifica que el backend esté activo en el puerto 5000.'
          : e.message
      );
    } finally {
      setCargando(false);
    }
  }, [dias]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const actualizar = (id, cambios) =>
    setTraslados((prev) => prev.map((t) => (t.id === id ? { ...t, ...cambios } : t)));

  const sucursales = [...new Set(traslados.map((t) => t.destino))].sort();
  // Si la sucursal elegida ya no tiene sugerencias tras recalcular, se vuelve a "todas".
  const sucursalActiva = sucursales.includes(sucursal) ? sucursal : 'todas';
  const deSucursal = sucursalActiva === 'todas' ? traslados : traslados.filter((t) => t.destino === sucursalActiva);
  const pendientes = deSucursal.filter((t) => t.estado === 'pendiente');
  const visibles = filtro === 'todos' ? deSucursal : deSucursal.filter((t) => t.estado === filtro);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Hola, {usuario.nombre.split(' ')[0]} 👋</p>
          <h1 className="text-2xl font-semibold text-slate-900">Bitácora de traslados</h1>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="horizonte" className="text-sm text-slate-500">
            Cubrir demanda de
          </label>
          <select
            id="horizonte"
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
            disabled={cargando}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            {HORIZONTES.map((d) => (
              <option key={d} value={d}>
                {d} días
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

      <WidgetVentas onVerDesglose={onVerVentas} />

      {error ? (
        <div role="alert" className="flex items-start gap-3 rounded-xl bg-red-50 p-4 text-red-800 ring-1 ring-red-200">
          <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <p className="flex-1 text-sm">{error}</p>
          <button onClick={cargar} className="text-sm font-medium underline underline-offset-2">
            Reintentar
          </button>
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded-xl bg-slate-900 text-white p-4 sm:p-5">
          <Sparkles className="h-5 w-5 shrink-0 text-amber-300 mt-0.5" />
          <div>
            <p className="font-medium">
              {cargando
                ? 'Analizando ventas e inventario...'
                : `El sistema generó ${traslados.length} borradores de traslado`}
            </p>
            <p className="text-sm text-slate-300">
              Del Almacén Principal a {sucursales.length > 1 ? `${sucursales.length} sucursales` : 'la sucursal'}, para
              cubrir {dias} días de demanda según el ritmo de ventas de cada una.{' '}
              {usuario.rol === 'gerente'
                ? 'Revisa y aprueba los pendientes.'
                : 'Ajusta las cantidades antes de enviarlos a aprobación.'}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Kpi icono={Clock} etiqueta="Pendientes de aprobación" valor={pendientes.length} acento="bg-amber-50 text-amber-600" />
        <Kpi
          icono={CheckCircle2}
          etiqueta="Aprobados en esta sesión"
          valor={deSucursal.filter((t) => t.estado === 'aprobado').length}
          acento="bg-emerald-50 text-emerald-600"
        />
        <Kpi
          icono={Flame}
          etiqueta="Pendientes clase A (críticos)"
          valor={pendientes.filter((t) => t.clasificacion_abc === 'A').length}
          acento="bg-red-50 text-red-600"
        />
      </div>

      <section className="space-y-3">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {sucursales.length > 1 && (
            <select
              aria-label="Sucursal destino"
              value={sucursalActiva}
              onChange={(e) => setSucursal(e.target.value)}
              className="rounded-full border-0 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-900"
            >
              <option value="todas">Todas las sucursales</option>
              {sucursales.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          )}
          {FILTROS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFiltro(f.id)}
              className={`whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition ${
                filtro === f.id
                  ? 'bg-slate-900 text-white'
                  : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
              }`}
            >
              {f.texto}
            </button>
          ))}
        </div>

        {!error && <TransferList traslados={visibles} cargando={cargando} rol={usuario.rol} onActualizar={actualizar} />}
      </section>
    </div>
  );
}
