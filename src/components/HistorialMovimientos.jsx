import { useState } from 'react';
import { AlertTriangle, Ban, History, PackageCheck, Search, Truck } from 'lucide-react';
import { fechaHora } from './traslados/estados.js';

// Categoría de cada evento de movimiento (el backend solo envía estos tipos, ver EVENTOS_MOVIMIENTO).
export const CATEGORIAS = {
  ENTRADA: { texto: 'Entradas', etiqueta: 'Entrada', icono: PackageCheck, clase: 'bg-emerald-50 text-emerald-800 ring-emerald-200', tipos: ['recibido'] },
  SALIDA: { texto: 'Salidas', etiqueta: 'Salida', icono: Truck, clase: 'bg-indigo-50 text-indigo-800 ring-indigo-200', tipos: ['despachado'] },
  RECHAZADO: { texto: 'Rechazados', etiqueta: 'Rechazado', icono: Ban, clase: 'bg-slate-100 text-slate-700 ring-slate-200', tipos: ['rechazado', 'descartado'] },
  DISCREPANCIA: {
    texto: 'Discrepancias', etiqueta: 'Discrepancia', icono: AlertTriangle, clase: 'bg-red-50 text-red-800 ring-red-200',
    tipos: ['recibido_con_diferencias'],
  },
};

export const categoriaDe = (tipo) => Object.keys(CATEGORIAS).find((c) => CATEGORIAS[c].tipos.includes(tipo));

const productos = (e) =>
  `${e.traslado.total_articulos} ${e.traslado.total_articulos === 1 ? 'artículo' : 'artículos'}: ${e.traslado.articulos.join(', ')}${
    e.traslado.total_articulos > e.traslado.articulos.length ? '…' : ''
  }`;

function Etiqueta({ categoria }) {
  const { etiqueta, icono: Icono, clase } = CATEGORIAS[categoria];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${clase}`}>
      <Icono className="h-3.5 w-3.5" aria-hidden="true" /> {etiqueta}
    </span>
  );
}

const Motivo = ({ e }) =>
  e.detalle?.comentario && CATEGORIAS.RECHAZADO.tipos.includes(e.tipo) ? (
    <span className="block text-xs text-slate-500">Motivo: {e.detalle.comentario}</span>
  ) : null;

const CAMPO = 'rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900';

export default function HistorialMovimientos({ eventos, onAbrir }) {
  const [categoria, setCategoria] = useState('TODOS');
  const [busqueda, setBusqueda] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');

  const items = eventos
    .map((e) => ({ ...e, categoria: categoriaDe(e.tipo) }))
    .filter((e) => e.categoria);
  const q = busqueda.trim().toLowerCase();
  const visibles = items.filter((e) => {
    const dia = e.fecha.slice(0, 10);
    const texto = [e.traslado.folio, e.traslado.origen, e.traslado.destino, ...(e.codigos ?? [])].join(' ').toLowerCase();
    return (categoria === 'TODOS' || e.categoria === categoria) && (!q || texto.includes(q)) &&
      (!desde || dia >= desde) && (!hasta || dia <= hasta);
  });
  const cuenta = (c) => items.filter((e) => e.categoria === c).length;

  return (
    <section className="rounded-xl bg-white ring-1 ring-slate-200">
      <div className="space-y-3 border-b border-slate-100 px-4 py-3">
        <h2 className="inline-flex items-center gap-2 font-semibold text-slate-900">
          <History className="h-4 w-4 text-slate-400" /> Historial de movimientos
        </h2>
        <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0" role="group" aria-label="Tipo de movimiento">
          {[['TODOS', 'Todos', items.length], ...Object.entries(CATEGORIAS).map(([id, c]) => [id, c.texto, cuenta(id)])].map(
            ([id, texto, n]) => (
              <button
                key={id}
                type="button"
                aria-pressed={categoria === id}
                onClick={() => setCategoria(id)}
                className={`shrink-0 rounded-full px-3 py-1 text-sm font-medium transition ${
                  categoria === id ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {texto} <span className={categoria === id ? 'text-slate-300' : 'text-slate-400'}>{n}</span>
              </button>
            ),
          )}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="relative flex-1">
            <span className="sr-only">Buscar por folio, código de producto o sucursal</span>
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Folio (TR-00012), código o sucursal"
              className={`${CAMPO} w-full pl-8`}
            />
          </label>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <label className="flex items-center gap-1.5">
              Desde <input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} className={CAMPO} />
            </label>
            <label className="flex items-center gap-1.5">
              Hasta <input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} className={CAMPO} />
            </label>
          </div>
        </div>
      </div>

      {visibles.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-slate-400">
          {items.length === 0 ? 'Sin movimientos de mercancía todavía.' : 'Ningún movimiento coincide con los filtros.'}
        </p>
      ) : (
        <>
          {/* Móvil */}
          <ul className="divide-y divide-slate-100 md:hidden">
            {visibles.map((e) => (
              <li key={e.id}>
                <button onClick={() => onAbrir(e.traslado.id)} className="block w-full px-4 py-3 text-left text-sm hover:bg-slate-50">
                  <div className="flex items-center justify-between gap-2">
                    <Etiqueta categoria={e.categoria} />
                    <span className="font-mono text-xs text-slate-700">{e.traslado.folio}</span>
                  </div>
                  <p className="mt-1.5 text-slate-900">
                    {e.traslado.origen} → {e.traslado.destino}
                  </p>
                  <p className="truncate text-xs text-slate-500">{productos(e)}</p>
                  <Motivo e={e} />
                  <p className="mt-1 text-[11px] text-slate-400">
                    {e.usuario} · {fechaHora(e.fecha)}
                  </p>
                </button>
              </li>
            ))}
          </ul>

          {/* Escritorio */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2">Tipo</th>
                  <th className="px-4 py-2">Folio</th>
                  <th className="px-4 py-2">Origen → destino</th>
                  <th className="px-4 py-2">Productos</th>
                  <th className="px-4 py-2">Fecha</th>
                  <th className="px-4 py-2">Usuario</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibles.map((e) => (
                  <tr key={e.id} className="align-top hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      <Etiqueta categoria={e.categoria} />
                    </td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => onAbrir(e.traslado.id)} className="font-mono text-xs text-slate-900 underline-offset-2 hover:underline">
                        {e.traslado.folio}
                      </button>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-slate-700">
                      {e.traslado.origen} → {e.traslado.destino}
                    </td>
                    <td className="max-w-xs px-4 py-2.5 text-slate-600">
                      <span className="block truncate">{productos(e)}</span>
                      <Motivo e={e} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">{fechaHora(e.fecha)}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">{e.usuario}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
