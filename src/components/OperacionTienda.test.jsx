import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider } from '../auth/AuthContext.jsx';
import { AvisosProvider } from './ui/Avisos.jsx';
import GestionLogistica from './GestionLogistica.jsx';
import ConsultaArticulos from './ConsultaArticulos.jsx';

const linea = (id, nombre, aprobada, despachada = null) => ({
  id, articulo_codigo: `C${id}`, articulo_nombre: nombre, clasificacion_abc: 'A', cantidad_sugerida: aprobada,
  cantidad_aprobada: aprobada, cantidad_despachada: despachada, cantidad_recibida: null, diferencia: null,
});

const documento = (id, estado, origen, destino, lineas) => ({
  id, folio: `TR-0000${id}`, estado, origen, destino, version: 4, total_articulos: lineas.length,
  total_unidades: lineas.reduce((s, l) => s + l.cantidad_aprobada, 0), articulos: lineas.map((l) => l.articulo_nombre),
  actualizado_en: '2026-10-18T09:00:00', lineas, eventos: [], acciones: [],
});

const POR_DESPACHAR = documento(1, 'aprobado', 'Almacén Principal', 'Barcelona', [linea(11, 'Balanza', 5), linea(12, 'Pico dosificador', 3)]);
const EN_TRANSITO = documento(2, 'despachado', 'Almacén Principal', 'Barcelona', [linea(21, 'Palito burbuja', 10, 10)]);

function servidor() {
  const llamadas = [];
  const json = (cuerpo) => ({ ok: true, status: 200, json: async () => cuerpo });
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, opciones = {}) => {
      llamadas.push({ url, opciones });
      if (url.includes('/acciones')) {
        const { accion } = JSON.parse(opciones.body);
        return json({ success: true, traslado: { ...(accion === 'despachar' ? POR_DESPACHAR : EN_TRANSITO), estado: accion === 'despachar' ? 'despachado' : 'recibido' } });
      }
      if (url.includes('/api/traslados/1')) return json({ success: true, traslado: POR_DESPACHAR });
      if (url.includes('/api/traslados/2')) return json({ success: true, traslado: EN_TRANSITO });
      if (url.startsWith('/api/traslados?')) {
        const items = url.includes('grupo=por_despachar') ? [POR_DESPACHAR] : [EN_TRANSITO];
        return json({ success: true, items, total: items.length });
      }
      if (url.startsWith('/api/tasas')) return json({ success: true, bcv: { valor: 40, fecha: '2026-10-18' }, interna: { valor: 50, fecha: '2026-10-18' } });
      if (url.startsWith('/api/inventario/stock')) {
        return json({ success: true, items: [{ codigo: 'B1', nombre: 'Balanza', grupo: 'HOGAR', existencias: [
          { ubicacion: 'Almacén Principal', existencia: 9, precio_usd: 9 },
          { ubicacion: 'Barcelona', existencia: 2, precio_usd: 10 },
        ] }] });
      }
      return json({ success: true });
    })
  );
  return llamadas;
}

const sesion = (usuario) => localStorage.setItem('soriega.sesion', JSON.stringify({ usuario }));
const montar = (vista) =>
  render(
    <AuthProvider>
      <AvisosProvider>{vista}</AvisosProvider>
    </AuthProvider>
  );

beforeEach(() => localStorage.clear());

describe('Despacho y recepción', () => {
  it('el embalador despacha desde el almacén tras confirmar, con las cantidades aprobadas', async () => {
    const llamadas = servidor();
    sesion('almacen01');
    montar(<GestionLogistica />);

    expect(await screen.findByRole('tab', { name: /Por despachar/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /En tránsito/ })).toBeInTheDocument();
    const lista = llamadas.find((l) => l.url.includes('grupo=por_despachar')).url;
    expect(lista).toContain('origen=Almac%C3%A9n+Principal');

    await userEvent.click(await screen.findByRole('button', { name: /Registrar despacho/ }));
    const hoja = await screen.findByRole('dialog');
    // Cancelar no ejecuta nada: protege de toques accidentales.
    await userEvent.click(within(hoja).getByRole('button', { name: 'Cancelar' }));
    expect(llamadas.some((l) => l.url.includes('/acciones'))).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: /Registrar despacho/ }));
    const otra = await screen.findByRole('dialog');
    await userEvent.click(await within(otra).findByRole('button', { name: 'Restar 1 a Despachada: Pico dosificador' }));
    await userEvent.click(within(otra).getByRole('button', { name: 'Confirmar' }));

    expect(await screen.findByText(/TR-00001 despachado/)).toBeInTheDocument();
    const accion = llamadas.find((l) => l.url.includes('/acciones'));
    expect(JSON.parse(accion.opciones.body)).toMatchObject({ accion: 'despachar', version: 4, cantidades: { 11: 5, 12: 2 } });
  });

  it('el piso de venta solo recibe lo que llega a su tienda y una diferencia exige observaciones', async () => {
    const llamadas = servidor();
    sesion('tienda01');
    montar(<GestionLogistica />);

    await screen.findByRole('button', { name: /Confirmar recepción/ });
    expect(screen.queryByRole('tab')).not.toBeInTheDocument(); // sin permiso de despacho
    expect(screen.queryByRole('button', { name: /Registrar despacho/ })).not.toBeInTheDocument();
    expect(llamadas.find((l) => l.url.includes('grupo=en_transito')).url).toContain('destino=Barcelona');

    await userEvent.click(screen.getByRole('button', { name: /Confirmar recepción/ }));
    const hoja = await screen.findByRole('dialog');
    await userEvent.click(await within(hoja).findByRole('button', { name: 'Restar 1 a Recibida: Palito burbuja' }));
    await userEvent.click(within(hoja).getByRole('button', { name: 'Confirmar' }));
    expect(within(hoja).getByText('Describe qué llegó distinto a lo despachado.')).toBeInTheDocument();
    expect(llamadas.some((l) => l.url.includes('/acciones'))).toBe(false);

    await userEvent.type(within(hoja).getByRole('textbox'), 'Una caja rota');
    await userEvent.click(within(hoja).getByRole('button', { name: 'Confirmar' }));
    await waitFor(() => expect(llamadas.some((l) => l.url.includes('/acciones'))).toBe(true));
    const accion = llamadas.find((l) => l.url.includes('/acciones'));
    expect(JSON.parse(accion.opciones.body)).toMatchObject({ accion: 'recibir', cantidades: { 21: 9 }, comentario: 'Una caja rota' });
  });
});

describe('Precios y stock', () => {
  it('muestra el precio a tasa interna (PRECIO1EX + IVA), en bolívares y a tasa BCV', async () => {
    servidor();
    sesion('tienda01');
    montar(<ConsultaArticulos />);
    await userEvent.type(screen.getByRole('searchbox'), 'bal');
    await screen.findByText('Balanza');
    // Barcelona: 10 sin IVA -> $11,60 a tasa interna; x 50 (interna) = Bs 580,00; / 40 (BCV) = $14,50.
    expect(screen.getByText('11,60')).toBeInTheDocument();
    expect(screen.getByText('580,00')).toBeInTheDocument();
    expect(screen.getByText('14,50')).toBeInTheDocument();
    expect(screen.getByText('Sin IVA: $10,00')).toBeInTheDocument();
    // En la misma tarjeta, las existencias con la ubicación del usuario marcada y el reporte de discrepancias.
    expect(screen.getByText('tu ubicación')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /No coincide/ })).toBeInTheDocument();
  });
});
