import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HistorialMovimientos from './HistorialMovimientos.jsx';

const traslado = (id, origen, destino, articulos) => ({
  id, folio: `TR-${String(id).padStart(5, '0')}`, origen, destino, total_articulos: articulos.length, articulos,
});

// Un movimiento de cada categoría, tal como los envía /api/dashboard.
const EVENTOS = [
  { id: 1, tipo: 'recibido', usuario: 'Tienda Barcelona', fecha: '2026-11-10T09:00:00', detalle: {},
    traslado: traslado(1, 'Almacén Principal', 'Barcelona', ['Aceite 1L']), codigos: ['A1'] },
  { id: 2, tipo: 'despachado', usuario: 'Embalador Almacén', fecha: '2026-11-08T15:30:00', detalle: {},
    traslado: traslado(2, 'Almacén Principal', 'Maturín', ['Arroz 1kg']), codigos: ['R7'] },
  { id: 3, tipo: 'rechazado', usuario: 'Carlos Ramírez', fecha: '2026-11-05T11:00:00', detalle: { comentario: 'Sin transporte' },
    traslado: traslado(3, 'Almacén Principal', 'Barcelona', ['Harina']), codigos: ['H2'] },
  { id: 4, tipo: 'descartado', usuario: 'María González', fecha: '2026-11-01T08:00:00', detalle: {},
    traslado: traslado(4, 'Almacén Principal', 'Puerto La Cruz', ['Azúcar']), codigos: ['Z9'] },
  { id: 5, tipo: 'recibido_con_diferencias', usuario: 'Tienda Barcelona', fecha: '2026-10-28T17:00:00', detalle: {},
    traslado: traslado(5, 'Almacén Principal', 'Barcelona', ['Café']), codigos: ['C3'] },
];

const montar = () => {
  const onAbrir = vi.fn();
  render(<HistorialMovimientos eventos={EVENTOS} onAbrir={onAbrir} />);
  return onAbrir;
};
// La tabla de escritorio: una fila de encabezado más una por movimiento visible.
const folios = () => within(screen.getByRole('table')).queryAllByRole('row').slice(1).map((r) => within(r).getByRole('button').textContent);

describe('Historial de movimientos', () => {
  it('filtra por categoría y muestra el motivo de los rechazados', async () => {
    montar();
    expect(folios()).toHaveLength(5);
    await userEvent.click(screen.getByRole('button', { name: /Rechazados/ }));
    expect(folios()).toEqual(['TR-00003', 'TR-00004']);
    expect(within(screen.getByRole('table')).getByText('Motivo: Sin transporte')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Entradas/ }));
    expect(folios()).toEqual(['TR-00001']);
    await userEvent.click(screen.getByRole('button', { name: /Discrepancias/ }));
    expect(folios()).toEqual(['TR-00005']);
  });

  it('busca por folio, código o sucursal y acota por fechas', async () => {
    montar();
    const buscar = screen.getByRole('searchbox');
    await userEvent.type(buscar, 'r7');
    expect(folios()).toEqual(['TR-00002']);
    await userEvent.clear(buscar);
    await userEvent.type(buscar, 'barcelona');
    expect(folios()).toEqual(['TR-00001', 'TR-00003', 'TR-00005']);
    await userEvent.clear(buscar);
    await userEvent.type(screen.getByLabelText('Desde'), '2026-11-05');
    expect(folios()).toEqual(['TR-00001', 'TR-00002', 'TR-00003']);
  });

  it('abre el traslado al pulsar su folio', async () => {
    const onAbrir = montar();
    await userEvent.click(within(screen.getByRole('table')).getByRole('button', { name: 'TR-00002' }));
    expect(onAbrir).toHaveBeenCalledWith(2);
    expect(onAbrir).toHaveBeenCalledTimes(1);
  });
});
