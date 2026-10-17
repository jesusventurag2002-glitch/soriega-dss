import { useEffect, useState } from 'react';
import { Sparkles, Clock, CheckCircle2, Flame } from 'lucide-react';
import TransferList from './TransferList.jsx';
import { TRASLADOS_SUGERIDOS } from '../data/mockData.js';

const FILTROS = [
  { id: 'todos', texto: 'Todos' },
  { id: 'pendiente', texto: 'Pendientes' },
  { id: 'aprobado', texto: 'Aprobados' },
  { id: 'rechazado', texto: 'Rechazados' },
];

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

export default function Dashboard({ usuario }) {
  const [traslados, setTraslados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [filtro, setFiltro] = useState('todos');

  // Simula la llamada al backend. Reemplazar por fetch('/api/traslados/sugeridos').
  useEffect(() => {
    const t = setTimeout(() => {
      setTraslados(TRASLADOS_SUGERIDOS);
      setCargando(false);
    }, 700);
    return () => clearTimeout(t);
  }, []);

  const actualizar = (id, cambios) =>
    setTraslados((prev) => prev.map((t) => (t.id === id ? { ...t, ...cambios } : t)));

  const pendientes = traslados.filter((t) => t.estado === 'pendiente');
  const visibles = filtro === 'todos' ? traslados : traslados.filter((t) => t.estado === filtro);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-slate-500">Hola, {usuario.nombre.split(' ')[0]} 👋</p>
        <h1 className="text-2xl font-semibold text-slate-900">Bitácora de traslados</h1>
      </div>

      <div className="flex items-start gap-3 rounded-xl bg-slate-900 text-white p-4 sm:p-5">
        <Sparkles className="h-5 w-5 shrink-0 text-amber-300 mt-0.5" />
        <div>
          <p className="font-medium">El sistema generó {traslados.length} borradores de traslado</p>
          <p className="text-sm text-slate-300">
            Basados en stock actual, punto de reorden y rotación ABC.{' '}
            {usuario.rol === 'gerente'
              ? 'Revisa y aprueba los pendientes.'
              : 'Ajusta las cantidades antes de enviarlos a aprobación.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Kpi icono={Clock} etiqueta="Pendientes de aprobación" valor={pendientes.length} acento="bg-amber-50 text-amber-600" />
        <Kpi
          icono={CheckCircle2}
          etiqueta="Aprobados hoy"
          valor={traslados.filter((t) => t.estado === 'aprobado').length}
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

        <TransferList traslados={visibles} cargando={cargando} rol={usuario.rol} onActualizar={actualizar} />
      </section>
    </div>
  );
}
