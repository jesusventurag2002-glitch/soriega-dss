import { Boxes, LogOut } from 'lucide-react';
import AlertBell from './AlertBell.jsx';

export default function Layout({ usuario, onLogout, children }) {
  const iniciales = usuario.nombre
    .split(' ')
    .map((p) => p[0])
    .join('');

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-slate-900 text-white flex items-center justify-center">
              <Boxes className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <p className="font-semibold text-slate-900">Soriega DSS</p>
              <p className="hidden sm:block text-xs text-slate-500">Logística e Inventario</p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <AlertBell />

            <div className="flex items-center gap-3 pl-2 sm:pl-4 border-l border-slate-200">
              <div className="h-9 w-9 rounded-full bg-slate-200 text-slate-700 text-sm font-semibold flex items-center justify-center">
                {iniciales}
              </div>
              <div className="hidden md:block leading-tight">
                <p className="text-sm font-medium text-slate-900">{usuario.nombre}</p>
                <p className="text-xs text-slate-500">{usuario.etiqueta}</p>
              </div>
              <button
                onClick={onLogout}
                title="Cerrar sesión"
                className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition"
              >
                <LogOut className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-6">{children}</main>
    </div>
  );
}
