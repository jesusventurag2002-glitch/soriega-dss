import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TrasladosModulo, { FILTROS_INICIALES } from './TrasladosModulo.jsx';
import { AvisosProvider } from '../ui/Avisos.jsx';

const linea = (id, codigo, nombre, sugerida) => ({
  id, articulo_codigo: codigo, articulo_nombre: nombre, clasificacion_abc: 'A', cantidad_sugerida: sugerida,
  cantidad_aprobada: null, cantidad_despachada: null, cantidad_recibida: null, diferencia: null,
  stock_origen: 100, stock_destino: 2, cobertura_dias: 1,
});

// Un documento con dos artículos por aprobar.
const base = {
  id: 7, folio: 'TR-00007', tipo: 'reposicion', origen: 'Almacén Principal', destino: 'Barcelona',
  estado: 'pendiente_aprobacion', total_articulos: 2, total_unidades: 43, abc: { A: 2, B: 0, C: 0 }, clasificacion_abc: 'A',
  con_diferencias: 0, articulos: ['Aceite 1L', 'Jabón azul'], horizonte_dias: 15, motivo_rechazo: null, observaciones: null,
  creado_por: 'María', creado_en: '2026-10-17T10:00:00', actualizado_en: '2026-10-17T10:00:00', version: 2,
  acciones: ['aprobar', 'rechazar'], editable: false, retirable: true,
  lineas: [linea(81, '1001', 'Aceite 1L', 28), linea(82, '2002', 'Jabón azul', 15)], eventos: [],
};

const conteos = (n) => ({ activos: n, borradores: 0, por_aprobar: n, por_despachar: 0, en_transito: 0, por_cerrar: 0, cerrados: 0, rechazados: 0, todos: n });

// Servidor simulado: la bandeja "por aprobar" contiene el traslado mientras siga pendiente.
function servidor({ respuestaAccion } = {}) {
  let traslado = { ...base };
  const llamadas = [];
  const fetch = vi.fn(async (url, opciones = {}) => {
    llamadas.push({ url, opciones });
    const json = (status, cuerpo) => ({ ok: status < 400, status, json: async () => cuerpo });
    if (/\/api\/traslados\/\d+$/.test(url)) return json(200, { success: true, traslado });
    if (url.includes('/acciones')) {
      if (respuestaAccion) return respuestaAccion(traslado);
      const { accion, motivo } = JSON.parse(opciones.body);
      traslado = { ...traslado, version: traslado.version + 1, acciones: [],
        estado: accion === 'aprobar' ? 'aprobado' : 'rechazado', motivo_rechazo: motivo ?? null };
      return json(200, { success: true, traslado: { ...traslado, eventos: [] } });
    }
    const pendiente = traslado.estado === 'pendiente_aprobacion';
    return json(200, {
      success: true, items: pendiente ? [traslado] : [], total: pendiente ? 1 : 0, pagina: 1, paginas: 1, por_pagina: 25,
      conteos: conteos(pendiente ? 1 : 0), opciones: { origenes: ['Almacén Principal'], destinos: ['Barcelona', 'Maturín'] },
    });
  });
  vi.stubGlobal('fetch', fetch);
  return { llamadas, fetch };
}

// Los filtros viven fuera del módulo (como en App), igual que en la aplicación real.
function Contenedor({ inicial }) {
  const [filtros, setFiltros] = useState(inicial);
  const [detalle, setDetalle] = useState(null);
  return (
    <AvisosProvider>
      <TrasladosModulo filtros={filtros} onFiltros={setFiltros} detalleId={detalle} onDetalle={setDetalle} />
      <output data-testid="filtros">{JSON.stringify(filtros)}</output>
    </AvisosProvider>
  );
}

const filtrosConContexto = { ...FILTROS_INICIALES, grupo: 'por_aprobar', q: 'aceite', destino: 'Barcelona' };
const tabla = () => screen.getByRole('table');

describe('Bandeja de traslados', () => {
  it('aprobar actualiza el registro y conserva pestaña, búsqueda y filtros', async () => {
    const { llamadas } = servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    await userEvent.click(await within(await screen.findByRole('table')).findByRole('button', { name: /aprobar/i }));

    expect(await screen.findByText('TR-00007 aprobado')).toBeInTheDocument();
    const accion = llamadas.find((l) => l.url.includes('/acciones'));
    expect(JSON.parse(accion.opciones.body)).toMatchObject({ accion: 'aprobar', version: 2 });
    expect(accion.opciones.headers['X-Rol']).toBeUndefined(); // sin login en la prueba no se inventa un rol

    // El registro sale de "Por aprobar" pero el usuario sigue en la misma vista y con los mismos filtros.
    expect(await screen.findByText('Ningún traslado coincide con los filtros')).toBeInTheDocument();
    expect(JSON.parse(screen.getByTestId('filtros').textContent)).toEqual(filtrosConContexto);
    expect(screen.getByRole('tab', { name: /por aprobar/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('searchbox')).toHaveValue('aceite');
    expect(screen.getByRole('combobox', { name: 'Destino' })).toHaveValue('Barcelona');
    const ultimaLista = llamadas.filter((l) => l.url.startsWith('/api/traslados?')).at(-1).url;
    expect(ultimaLista).toContain('q=aceite');
    expect(ultimaLista).toContain('destino=Barcelona');
  });

  it('un conflicto del servidor muestra el estado real y no un éxito falso', async () => {
    servidor({
      respuestaAccion: (t) => ({
        ok: false, status: 409,
        json: async () => ({ success: false, error: 'TR-00007 cambió mientras lo revisabas (ahora está «Aprobado»).',
          traslado: { ...t, estado: 'aprobado', version: 3, acciones: [], eventos: [] } }),
      }),
    });
    render(<Contenedor inicial={filtrosConContexto} />);
    await userEvent.click(await within(await screen.findByRole('table')).findByRole('button', { name: /aprobar/i }));

    expect(await screen.findByText('No se pudo aprobar TR-00007')).toBeInTheDocument();
    expect(screen.queryByText('TR-00007 aprobado')).not.toBeInTheDocument();
  });

  it('rechazar exige un motivo antes de enviar la solicitud', async () => {
    const { llamadas } = servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    await userEvent.click(await within(await screen.findByRole('table')).findByRole('button', { name: /rechazar/i }));
    const dialogo = screen.getByRole('alertdialog');
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Rechazar' }));
    expect(within(dialogo).getByText(/al menos 3 caracteres/)).toBeInTheDocument();
    expect(llamadas.some((l) => l.url.includes('/acciones'))).toBe(false);

    await userEvent.type(within(dialogo).getByRole('textbox'), 'Hay compra en camino');
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Rechazar' }));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    const accion = llamadas.find((l) => l.url.includes('/acciones'));
    expect(JSON.parse(accion.opciones.body)).toMatchObject({ accion: 'rechazar', motivo: 'Hay compra en camino' });
  });

  it('un doble clic no envía la acción dos veces', async () => {
    let liberar;
    const { llamadas } = servidor({
      respuestaAccion: (t) =>
        new Promise((resolve) => {
          liberar = () => resolve({ ok: true, status: 200, json: async () => ({ success: true, traslado: { ...t, estado: 'aprobado', version: 3, acciones: [], eventos: [] } }) });
        }),
    });
    render(<Contenedor inicial={filtrosConContexto} />);
    const boton = await within(await screen.findByRole('table')).findByRole('button', { name: /aprobar/i });
    await userEvent.click(boton);
    await userEvent.click(boton);
    expect(boton).toBeDisabled();
    liberar();
    await screen.findByText('TR-00007 aprobado');
    expect(llamadas.filter((l) => l.url.includes('/acciones'))).toHaveLength(1);
  });

  it('solo muestra las acciones que el backend permite para el rol', async () => {
    servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    const filas = within(await screen.findByRole('table'));
    await filas.findByText('Aceite 1L, Jabón azul');
    expect(filas.queryByRole('button', { name: /despachar/i })).not.toBeInTheDocument();
    expect(filas.queryByRole('button', { name: /^enviar/i })).not.toBeInTheDocument();
  });

  it('muestra una fila por documento con la ruta y el total de artículos', async () => {
    servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    const filas = within(await screen.findByRole('table'));
    expect(await filas.findByText('TR-00007')).toBeInTheDocument();
    expect(filas.getByText('2 artículos')).toBeInTheDocument();
    expect(filas.getByText('43')).toBeInTheDocument();
    expect(filas.getAllByRole('row')).toHaveLength(2); // encabezado + un documento
  });

  it('el detalle aprueba el documento completo con las cantidades ajustadas por artículo', async () => {
    const { llamadas } = servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    await userEvent.click(await within(await screen.findByRole('table')).findByText('TR-00007'));

    const panel = await screen.findByRole('dialog', { name: 'Traslado TR-00007' });
    const jabon = await within(panel).findByRole('spinbutton', { name: 'A aprobar: Jabón azul' });
    expect(jabon).toHaveValue(15);
    await userEvent.clear(jabon);
    await userEvent.type(jabon, '10');
    await userEvent.click(within(panel).getByRole('button', { name: 'Aprobar traslado completo' }));

    expect(await screen.findByText('TR-00007 aprobado')).toBeInTheDocument();
    const accion = llamadas.find((l) => l.url.includes('/acciones'));
    expect(JSON.parse(accion.opciones.body)).toMatchObject({ accion: 'aprobar', version: 2, cantidades: { 81: 28, 82: 10 } });
  });

  it('quitar un artículo pide confirmación y llama al servidor solo para esa línea', async () => {
    const { llamadas, fetch } = servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    await userEvent.click(await within(await screen.findByRole('table')).findByText('TR-00007'));
    const panel = await screen.findByRole('dialog', { name: 'Traslado TR-00007' });
    fetch.mockImplementationOnce(async (url, opciones) => {
      llamadas.push({ url, opciones });
      return { ok: true, status: 200, json: async () => ({ success: true, traslado: { ...base, version: 3, total_articulos: 1, lineas: [base.lineas[0]] } }) };
    });
    await userEvent.click(await within(panel).findByRole('button', { name: 'Quitar Jabón azul del traslado' }));
    await userEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Quitar artículo' }));

    expect(await screen.findByText('Jabón azul quitado de TR-00007')).toBeInTheDocument();
    const retiro = llamadas.find((l) => l.opciones.method === 'DELETE');
    expect(retiro.url).toBe('/api/traslados/7/lineas/82');
    expect(JSON.parse(retiro.opciones.body)).toMatchObject({ version: 2 });
  });

  it('filtrar la bandeja por clase A hace que generar proponga solo clase A', async () => {
    const { llamadas } = servidor();
    render(<Contenedor inicial={filtrosConContexto} />);
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Clasificación ABC' }), 'A');
    expect(screen.getByRole('combobox', { name: 'Clases ABC a proponer' })).toHaveValue('A');
    await userEvent.click(screen.getByRole('button', { name: /generar propuestas/i }));
    await waitFor(() => expect(llamadas.some((l) => l.url.includes('/generar'))).toBe(true));
    const generar = llamadas.find((l) => l.url.includes('/generar'));
    expect(JSON.parse(generar.opciones.body)).toEqual({ dias: 15, clases: ['A'] });
  });
});
