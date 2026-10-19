import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AnalisisVentas from './AnalisisVentas.jsx';

const grupo = (nombre, total, costo, sinCosto = 0) => ({
  grupo: nombre, total, costo, utilidad: total - costo, margen: Math.round(((total - costo) / total) * 1000) / 10, ventas_sin_costo: sinCosto,
});

const todos = [grupo('VIVERES', 600, 400), grupo('LIMPIEZA', 300, 150), grupo('JUGUETES', 60, 20), grupo('PAPELERIA', 40, 0, 40)];
const datos = {
  success: true, fecha_corte: '2026-10-17', mes: 10, ano: 2026, meses_disponibles: [{ mes: 10, ano: 2026 }],
  total_mes: 1000, costo_mes: 570, utilidad_mes: 430, ventas_sin_costo_mes: 40, total_bruto: 1000, dias_sin_tasa_interna: 0,
  excepciones: [], grupos_principales: ['VIVERES', 'LIMPIEZA'],
  sucursales: [{
    sucursal: 'Barcelona', total: 1000, costo: 570, utilidad: 430, margen: 43, ventas_sin_costo: 40,
    grupos: [todos[0], todos[1], { ...grupo('OTROS', 100, 20, 40) }], todos_los_grupos: todos,
  }],
  ultimos_7_dias: [],
};

describe('Análisis de ventas', () => {
  it('muestra la utilidad del mes y, con el botón, todos los grupos sin agrupar en "Otros"', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => datos })));
    // jsdom no implementa ResizeObserver, que usan los gráficos.
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    render(<AnalisisVentas onVolver={() => {}} />);

    expect(await screen.findByText('Costo de lo vendido')).toBeInTheDocument();
    expect(screen.getAllByText('$430').length).toBeGreaterThan(0);
    expect(screen.getByText(/no traen costo en el reporte/)).toBeInTheDocument();
    expect(screen.queryByText('Juguetes')).not.toBeInTheDocument(); // está dentro de "Otros grupos"

    await userEvent.click(screen.getByRole('button', { name: 'Ver todos los grupos (4)' }));
    const tabla = screen.getByText('Todos los grupos · Sucursal Barcelona').closest('section');
    expect(within(tabla).getByText('Juguetes')).toBeInTheDocument();
    expect(within(tabla).getByText('Papeleria')).toBeInTheDocument();
    expect(within(tabla).getByLabelText('Ventas sin costo registrado')).toBeInTheDocument();

    // Ordenar por margen deja primero el grupo más rentable en proporción.
    await userEvent.click(within(tabla).getByRole('button', { name: 'Margen' }));
    const filas = within(tabla).getAllByRole('row').slice(1, -1);
    expect(within(filas[0]).getByText('Papeleria')).toBeInTheDocument();
  });
});
