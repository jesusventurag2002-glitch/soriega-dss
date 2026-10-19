import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../App.jsx';
import { AuthProvider, useAuth } from './AuthContext.jsx';

// Ninguna vista necesita datos reales para estas pruebas: el backend responde vacío.
function sinBackend() {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({ success: false, error: 'Sin backend' }) })));
}

const montar = () =>
  render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );

async function ingresar(usuario, clave) {
  await userEvent.type(screen.getByLabelText('Usuario'), usuario);
  await userEvent.type(screen.getByLabelText('Contraseña'), clave);
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
}

const menu = () =>
  within(screen.getByRole('navigation', { name: 'Menú principal' }))
    .getAllByRole('button')
    .map((b) => b.textContent.trim());

beforeEach(() => {
  localStorage.clear();
  sinBackend();
});

describe('Inicio de sesión', () => {
  it('rechaza credenciales incorrectas con un mensaje que no revela si el usuario existe', async () => {
    montar();
    await ingresar('gerente', 'mala');
    expect(screen.getByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.');
    await userEvent.clear(screen.getByLabelText('Usuario'));
    await ingresar('nadie', '123');
    expect(screen.getByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.');
    expect(localStorage.getItem('soriega.sesion')).toBeNull();
  });

  it('la sesión persiste al recargar y no guarda la contraseña', async () => {
    const { unmount } = montar();
    await ingresar('Gerente ', '123'); // sin distinguir mayúsculas ni espacios en el usuario
    expect(await screen.findByText('Carlos Ramírez')).toBeInTheDocument();
    expect(localStorage.getItem('soriega.sesion')).not.toContain('123');
    unmount();

    montar(); // recarga
    expect(screen.queryByRole('button', { name: 'Ingresar' })).not.toBeInTheDocument();
    expect(screen.getByText('Carlos Ramírez')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeInTheDocument();
    expect(localStorage.getItem('soriega.sesion')).toBeNull();
  });

  it('editar el rol en localStorage no otorga permisos: se toman de la lista de usuarios', () => {
    localStorage.setItem('soriega.sesion', JSON.stringify({ usuario: 'tienda01', rol: 'root' }));
    montar();
    expect(menu()).toEqual(['Precios y stock', 'Despacho y recepción', 'Discrepancias', 'Promociones']);
  });
});

describe('Menú por rol', () => {
  it.each([
    ['root', '28691009', ['Carga de datos', 'Usuarios']],
    ['compras', '123', ['Inicio', 'Traslados', 'Análisis de ventas', 'Capital estancado', 'Discrepancias']],
    ['gerente', '123', ['Inicio', 'Traslados', 'Análisis de ventas', 'Capital estancado', 'Discrepancias']],
    ['tienda01', '123', ['Precios y stock', 'Despacho y recepción', 'Discrepancias', 'Promociones']],
    ['almacen01', '123', ['Precios y stock', 'Despacho y recepción', 'Discrepancias', 'Promociones']],
  ])('%s solo ve sus módulos', async (usuario, clave, esperado) => {
    montar();
    await ingresar(usuario, clave);
    expect(menu()).toEqual(esperado);
  });
});

describe('Suspensión de usuarios', () => {
  it('root suspende a un usuario, que ya no puede iniciar sesión', async () => {
    montar();
    await ingresar('root', '28691009');
    await userEvent.click(screen.getByRole('button', { name: /Usuarios/ }));
    const fila = screen.getByText('tienda01').closest('tr');
    await userEvent.click(within(fila).getByRole('button', { name: 'Suspender' }));
    await userEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Suspender' }));
    expect(within(fila).getByText('Suspendido')).toBeInTheDocument();
    expect(within(screen.getByText('root').closest('tr')).queryByRole('button')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    await ingresar('tienda01', '123');
    expect(screen.getByRole('alert')).toHaveTextContent('suspendido');
  });

  it('una sesión guardada de un usuario suspendido no se restaura', () => {
    localStorage.setItem('soriega.sesion', JSON.stringify({ usuario: 'compras' }));
    localStorage.setItem('soriega.usuarios.suspendidos', JSON.stringify(['compras']));
    montar();
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeInTheDocument();
  });

  it('solo quien tiene el permiso puede suspender', async () => {
    let auth;
    function Espia() {
      auth = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Espia />
      </AuthProvider>
    );
    act(() => {
      auth.login('gerente', '123');
    });
    expect(() => auth.suspender('compras')).toThrow('No tienes permiso');
  });
});
