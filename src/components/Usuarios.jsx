import { useState } from 'react';
import { Ban, RotateCcw, Users } from 'lucide-react';
import Encabezado from './ui/Encabezado.jsx';
import Aviso from './ui/Aviso.jsx';
import Boton from './ui/Boton.jsx';
import Dialogo from './ui/Dialogo.jsx';
import { useAvisos } from './ui/Avisos.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import { ROLES } from '../auth/roles.js';

// Administración de usuarios (solo root). Suspender impide iniciar sesión y cierra la sesión abierta de ese usuario.
export default function Usuarios() {
  const { usuario: actual, usuarios, suspender, reactivar } = useAuth();
  const avisar = useAvisos();
  const [confirmar, setConfirmar] = useState(null);

  return (
    <div className="space-y-5">
      <Encabezado icono={Users} titulo="Usuarios" subtitulo="Acceso al sistema por rol. Un usuario suspendido no puede iniciar sesión." />

      <Aviso tono="advertencia">
        Usuarios de demostración: la suspensión se guarda solo en este navegador hasta que exista el backend de usuarios.
      </Aviso>

      <div className="overflow-x-auto rounded-xl bg-white ring-1 ring-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Usuario</th>
              <th className="px-4 py-3">Rol</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3 text-right">Acción</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {usuarios.map((u) => (
              <tr key={u.usuario}>
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-900">{u.nombre}</p>
                  <p className="font-mono text-xs text-slate-500">{u.usuario}</p>
                </td>
                <td className="px-4 py-3 text-slate-700">
                  {ROLES[u.rol]?.etiqueta ?? u.rol}
                  {u.sucursal && <span className="text-slate-500"> · {u.sucursal}</span>}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${
                      u.suspendido ? 'bg-red-50 text-red-700 ring-red-200' : 'bg-emerald-50 text-emerald-800 ring-emerald-200'
                    }`}
                  >
                    {u.suspendido ? 'Suspendido' : 'Activo'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {u.usuario === actual.usuario ? (
                    <span className="text-xs text-slate-400">Tu usuario</span>
                  ) : u.suspendido ? (
                    <Boton tamano="sm" icono={RotateCcw} onClick={() => setConfirmar({ u, suspender: false })}>
                      Reactivar
                    </Boton>
                  ) : (
                    <Boton tamano="sm" variante="peligro" icono={Ban} onClick={() => setConfirmar({ u, suspender: true })}>
                      Suspender
                    </Boton>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {confirmar && (
        <Dialogo
          titulo={`${confirmar.suspender ? 'Suspender' : 'Reactivar'} a ${confirmar.u.nombre}`}
          textoConfirmar={confirmar.suspender ? 'Suspender' : 'Reactivar'}
          varianteConfirmar={confirmar.suspender ? 'peligro' : 'primario'}
          onCancelar={() => setConfirmar(null)}
          onConfirmar={async () => {
            (confirmar.suspender ? suspender : reactivar)(confirmar.u.usuario);
            avisar({ tono: 'exito', titulo: `${confirmar.u.nombre} ${confirmar.suspender ? 'suspendido' : 'reactivado'}` });
            setConfirmar(null);
          }}
        >
          {confirmar.suspender
            ? `«${confirmar.u.usuario}» no podrá iniciar sesión y, si tiene una sesión abierta en este navegador, se cerrará.`
            : `«${confirmar.u.usuario}» podrá volver a iniciar sesión.`}
        </Dialogo>
      )}
    </div>
  );
}
