import { useState } from 'react';
import { Boxes, ClipboardList, BarChart3, ArrowRight } from 'lucide-react';

const ROLES = [
  {
    id: 'analista',
    titulo: 'Analista',
    descripcion: 'Revisa y ajusta borradores de traslado',
    icono: ClipboardList,
  },
  {
    id: 'gerente',
    titulo: 'Gerente',
    descripcion: 'Aprueba traslados y supervisa indicadores',
    icono: BarChart3,
  },
];

export default function Login({ onLogin }) {
  const [rol, setRol] = useState('analista');

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-100 via-white to-slate-200 px-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="h-14 w-14 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-lg">
            <Boxes className="h-7 w-7" />
          </div>
          <h1 className="mt-4 text-2xl font-semibold text-slate-900">Soriega DSS</h1>
          <p className="text-sm text-slate-500">Soporte a decisiones · Logística e Inventario</p>
        </div>

        <form
          className="bg-white rounded-2xl shadow-xl ring-1 ring-slate-200 p-6 space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            onLogin(rol);
          }}
        >
          <p className="text-sm font-medium text-slate-700">Selecciona tu perfil de acceso</p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {ROLES.map(({ id, titulo, descripcion, icono: Icono }) => {
              const activo = rol === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setRol(id)}
                  className={`text-left rounded-xl border p-4 transition ${
                    activo
                      ? 'border-slate-900 bg-slate-900 text-white shadow-md'
                      : 'border-slate-200 hover:border-slate-400 text-slate-700'
                  }`}
                >
                  <Icono className={`h-5 w-5 mb-2 ${activo ? 'text-white' : 'text-slate-500'}`} />
                  <p className="font-semibold">{titulo}</p>
                  <p className={`text-xs mt-1 ${activo ? 'text-slate-300' : 'text-slate-500'}`}>
                    {descripcion}
                  </p>
                </button>
              );
            })}
          </div>

          <button
            type="submit"
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-sm font-semibold text-white hover:bg-slate-800 transition"
          >
            Entrar <ArrowRight className="h-4 w-4" />
          </button>

          <p className="text-center text-xs text-slate-400">Demo · Inicio de sesión simulado (sin contraseña)</p>
        </form>
      </div>
    </div>
  );
}
