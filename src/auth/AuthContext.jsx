import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { establecerUsuario } from '../services/api.js';
import { USUARIOS_DEMO, datosPublicos } from './usuarios.js';
import { ROLES, puede as puedeRol } from './roles.js';

const CLAVE_SESION = 'soriega.sesion';
const CLAVE_SUSPENDIDOS = 'soriega.usuarios.suspendidos';

// localStorage puede no estar disponible (modo privado, almacenamiento bloqueado): la app sigue funcionando
// y solo se pierde la persistencia.
function leer(clave, defecto) {
  try {
    const valor = localStorage.getItem(clave);
    return valor ? JSON.parse(valor) : defecto;
  } catch {
    return defecto;
  }
}

function escribir(clave, valor) {
  try {
    if (valor == null) localStorage.removeItem(clave);
    else localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    /* sin persistencia */
  }
}

const buscar = (usuario) => USUARIOS_DEMO.find((u) => u.usuario === usuario);

// La sesión guardada solo identifica al usuario: nombre, rol y permisos se toman siempre de la lista de usuarios,
// así que editar localStorage no da más permisos. Un usuario suspendido o inexistente no recupera la sesión.
function restaurarSesion(suspendidos) {
  const sesion = leer(CLAVE_SESION, null);
  const u = sesion && buscar(sesion.usuario);
  return u && !suspendidos.includes(u.usuario) ? datosPublicos(u) : null;
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [suspendidos, setSuspendidos] = useState(() => leer(CLAVE_SUSPENDIDOS, []));
  const [usuario, setUsuario] = useState(() => {
    const u = restaurarSesion(leer(CLAVE_SUSPENDIDOS, []));
    // Se fija antes del primer render para que las primeras peticiones ya identifiquen al usuario.
    establecerUsuario(u);
    return u;
  });

  const cambiarUsuario = useCallback((u) => {
    establecerUsuario(u);
    setUsuario(u);
  }, []);

  const login = useCallback(
    (nombreUsuario, clave) => {
      const u = buscar(String(nombreUsuario ?? '').trim().toLowerCase());
      // Mismo mensaje si el usuario no existe o la clave es incorrecta: no revela qué usuarios existen.
      if (!u || u.clave !== clave) return { ok: false, error: 'Usuario o contraseña incorrectos.' };
      if (leer(CLAVE_SUSPENDIDOS, []).includes(u.usuario)) {
        return { ok: false, error: 'Tu usuario está suspendido. Contacta al administrador del sistema.' };
      }
      const publico = datosPublicos(u);
      escribir(CLAVE_SESION, { usuario: u.usuario, iniciada_en: new Date().toISOString() });
      cambiarUsuario(publico);
      return { ok: true, usuario: publico };
    },
    [cambiarUsuario]
  );

  const logout = useCallback(() => {
    escribir(CLAVE_SESION, null);
    cambiarUsuario(null);
  }, [cambiarUsuario]);

  const fijarSuspension = useCallback(
    (nombreUsuario, suspender) => {
      if (!puedeRol(usuario, 'usuarios')) throw new Error('No tienes permiso para administrar usuarios.');
      if (nombreUsuario === usuario.usuario) throw new Error('No puedes suspender tu propio usuario.');
      const actuales = leer(CLAVE_SUSPENDIDOS, []);
      const nuevos = suspender ? [...new Set([...actuales, nombreUsuario])] : actuales.filter((x) => x !== nombreUsuario);
      escribir(CLAVE_SUSPENDIDOS, nuevos);
      setSuspendidos(nuevos);
    },
    [usuario]
  );

  // Otra pestaña cerró sesión, entró con otro usuario o suspendió al usuario actual: se refleja aquí.
  useEffect(() => {
    const sincronizar = (e) => {
      if (e.key !== CLAVE_SESION && e.key !== CLAVE_SUSPENDIDOS) return;
      const nuevosSuspendidos = leer(CLAVE_SUSPENDIDOS, []);
      setSuspendidos(nuevosSuspendidos);
      cambiarUsuario(restaurarSesion(nuevosSuspendidos));
    };
    window.addEventListener('storage', sincronizar);
    return () => window.removeEventListener('storage', sincronizar);
  }, [cambiarUsuario]);

  const valor = useMemo(
    () => ({
      usuario,
      etiquetaRol: usuario ? ROLES[usuario.rol]?.etiqueta ?? usuario.rol : null,
      login,
      logout,
      puede: (permiso) => puedeRol(usuario, permiso),
      usuarios: USUARIOS_DEMO.map((u) => ({ ...datosPublicos(u), suspendido: suspendidos.includes(u.usuario) })),
      suspender: (nombreUsuario) => fijarSuspension(nombreUsuario, true),
      reactivar: (nombreUsuario) => fijarSuspension(nombreUsuario, false),
    }),
    [usuario, login, logout, suspendidos, fijarSuspension]
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>.');
  return contexto;
}
