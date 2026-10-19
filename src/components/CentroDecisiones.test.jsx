import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CentroDecisiones from './CentroDecisiones.jsx';

const datosBase = {
  success: true,
  sucursal: null,
  traslados: { borradores: 4, por_aprobar: 2, por_despachar: 0, en_transito: 1, con_diferencias: 0, por_cerrar: 0 },
  pendientes: {
    por_aprobar: [{ id: 3, folio: 'TR-00003', tipo: 'reposicion', clasificacion_abc: 'A', origen: 'Almacén Principal',
      destino: 'Barcelona', estado: 'pendiente_aprobacion', total_articulos: 1, total_unidades: 10, abc: { A: 1, B: 0, C: 0 },
      con_diferencias: 0, articulos: ['Aceite 1L'], actualizado_en: '2026-10-17T10:00:00' }],
    en_transito: [],
    con_diferencias: [],
  },
  criticos: { total: 0, dias_cobertura: 7, items: [] },
  capital_estancado: { total: 1500, articulos: 12, dias_min: 90, fecha_corte: '2026-10-16', consolidado: true },
  acciones_estancado: { pendientes: 0, items: [] },
  actividad: [],
  importaciones: [],
  datos: {
    sucursales: [
      { sucursal: 'Barcelona', inventario: { cargado: true, importado_en: '2026-10-17T20:00:00' }, ventas: { cargado: true, importado_en: null, datos_hasta: '2026-10-16' } },
      { sucursal: 'Maturín', inventario: { cargado: false, importado_en: null }, ventas: { cargado: true, importado_en: null, datos_hasta: '2026-10-15' } },
    ],
    almacen: { cargado: true, importado_en: null },
    tasas: { importado_en: null, datos_hasta: null },
  },
};

function montar(props = {}, datos = datosBase) {
  vi.stubGlobal('fetch', vi.fn(async (url) => ({
    ok: true, status: 200,
    // El widget de ventas consulta su propio endpoint; aquí responde sin datos.
    json: async () => (url.includes('/api/dashboard') ? datos : { success: false, error: 'Sin ventas' }),
  })));
  const onIrTraslados = vi.fn();
  const onIr = vi.fn();
  render(
    <CentroDecisiones usuario={{ nombre: 'Carlos Ramírez' }} sucursal="" onSucursal={() => {}} onIrTraslados={onIrTraslados}
      onAbrirTraslado={() => {}} onIr={onIr} {...props} />
  );
  return { onIrTraslados, onIr };
}

describe('Centro de decisiones', () => {
  it('cada indicador lleva a los registros que lo componen', async () => {
    const { onIrTraslados, onIr } = montar();
    await userEvent.click(await screen.findByRole('button', { name: /Por aprobar/ }));
    expect(onIrTraslados).toHaveBeenCalledWith({ grupo: 'por_aprobar' });
    await userEvent.click(screen.getByRole('button', { name: /Por recibir/ }));
    expect(onIrTraslados).toHaveBeenLastCalledWith({ grupo: 'en_transito' });
    await userEvent.click(screen.getByRole('button', { name: /Capital estancado/ }));
    expect(onIr).toHaveBeenCalledWith('estancado');
  });

  it('con una sucursal elegida, la navegación conserva ese contexto', async () => {
    const { onIrTraslados } = montar({ sucursal: 'Barcelona' });
    await userEvent.click(await screen.findByRole('button', { name: /Por aprobar/ }));
    expect(onIrTraslados).toHaveBeenCalledWith({ grupo: 'por_aprobar', sucursal: 'Barcelona' });
  });

  it('avisa cuando faltan datos de una sucursal en lugar de presentarlos como completos', async () => {
    montar();
    expect(await screen.findByText('Datos incompletos')).toBeInTheDocument();
    expect(screen.getByText(/Maturín: falta inventario/)).toBeInTheDocument();
  });

  it('sin pendientes no inventa alertas', async () => {
    montar({}, {
      ...datosBase,
      traslados: { borradores: 0, por_aprobar: 0, por_despachar: 0, en_transito: 0, con_diferencias: 0, por_cerrar: 0 },
      pendientes: { por_aprobar: [], en_transito: [], con_diferencias: [] },
    });
    expect(await screen.findByText('Nada requiere atención en esta vista')).toBeInTheDocument();
    expect(screen.queryByText('Propuestas por aprobar')).not.toBeInTheDocument();
  });
});
