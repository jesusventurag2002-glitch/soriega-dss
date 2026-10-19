import { useState } from 'react';
import { Boxes, Eye, EyeOff, LogIn, XCircle } from 'lucide-react';
import { useAuth } from '../auth/AuthContext.jsx';

const claseCampo =
  'mt-1 w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/20';

// Pantalla de inicio de sesión. Con una sesión guardada, App muestra directamente la aplicación.
export default function Login() {
  const { login } = useAuth();
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState(null);

  const ingresar = (e) => {
    e.preventDefault();
    if (!usuario.trim() || !clave) {
      setError('Escribe tu usuario y tu contraseña.');
      return;
    }
    const r = login(usuario, clave);
    if (!r.ok) {
      setError(r.error);
      setClave('');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 via-white to-slate-200 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg">
            <Boxes className="h-7 w-7" />
          </div>
          <h1 className="mt-4 text-2xl font-semibold text-slate-900">Soriega DSS</h1>
          <p className="text-sm text-slate-500">Soporte a decisiones · Logística e Inventario</p>
        </div>

        <form onSubmit={ingresar} noValidate className="space-y-4 rounded-2xl bg-white p-6 shadow-xl ring-1 ring-slate-200">
          <div>
            <h2 className="font-semibold text-slate-900">Iniciar sesión</h2>
            <p className="text-sm text-slate-500">Ingresa con tu usuario corporativo.</p>
          </div>

          {error && (
            <p role="alert" className="flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-700 ring-1 ring-red-200">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </p>
          )}

          <label className="block text-sm font-medium text-slate-700">
            Usuario
            <input
              type="text"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              autoFocus
              value={usuario}
              onChange={(e) => {
                setUsuario(e.target.value);
                setError(null);
              }}
              aria-invalid={!!error}
              className={claseCampo}
            />
          </label>

          <label className="block text-sm font-medium text-slate-700">
            Contraseña
            <span className="relative block">
              <input
                type={verClave ? 'text' : 'password'}
                name="password"
                autoComplete="current-password"
                value={clave}
                onChange={(e) => {
                  setClave(e.target.value);
                  setError(null);
                }}
                aria-invalid={!!error}
                className={`${claseCampo} pr-11`}
              />
              <button
                type="button"
                onClick={() => setVerClave((v) => !v)}
                aria-label={verClave ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                className="absolute right-1.5 top-1/2 mt-0.5 -translate-y-1/2 rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                {verClave ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </span>
          </label>

          <button
            type="submit"
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
          >
            <LogIn className="h-4 w-4" /> Ingresar
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-400">Entorno de demostración · usuarios simulados</p>
      </div>
    </div>
  );
}
