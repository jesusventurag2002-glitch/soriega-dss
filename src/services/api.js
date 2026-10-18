// Por defecto se usa la misma URL del frontend: el proxy de Vite reenvía /api al backend Flask,
// lo que permite abrir la app desde otros dispositivos de la red. Ajustable con VITE_API_URL en un .env.
const API_URL = import.meta.env.VITE_API_URL ?? '';

const ORDEN_ABC = { A: 0, B: 1, C: 2 };

// Sugerencias de traslado Almacén Principal (INVAL) -> Sucursal (INV), adaptadas al formato de la vista.
export async function obtenerTrasladosSugeridos(dias) {
  const respuesta = await fetch(`${API_URL}/api/logistica`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tipo_analisis: 'traslado', dias }),
  });
  const data = await respuesta.json();
  if (!data.success) throw new Error(data.error || 'No se pudieron obtener los traslados.');

  return data.resultados
    .map((r) => ({
      id: r.codigo,
      codigo: r.codigo,
      descripcion: r.nombre,
      clasificacion_abc: r.clasificacion_abc,
      origen: 'Almacén Principal',
      destino: 'Sucursal',
      stock_origen: r.disponible_almacen,
      stock_destino: r.stock_sucursal,
      cantidad_sugerida: r.cantidad,
      estado: 'pendiente',
    }))
    .sort(
      (a, b) =>
        (ORDEN_ABC[a.clasificacion_abc] ?? 3) - (ORDEN_ABC[b.clasificacion_abc] ?? 3) ||
        b.cantidad_sugerida - a.cantidad_sugerida
    );
}

// Artículos con stock sin ventas en los últimos `diasMin` días, ordenados por capital inmovilizado.
export async function obtenerCapitalEstancado(diasMin, limite = 100) {
  const respuesta = await fetch(`${API_URL}/api/capital_estancado?dias_min=${diasMin}&limite=${limite}`);
  const data = await respuesta.json();
  if (!data.success) throw new Error(data.error || 'No se pudo obtener el capital estancado.');
  return data;
}

// Ventas de un mes por sucursal y grupo. Sin periodo, el backend usa el mes de la última venta registrada.
export async function obtenerAnalisisVentas(periodo) {
  const query = periodo ? `?mes=${periodo.mes}&ano=${periodo.ano}` : '';
  const respuesta = await fetch(`${API_URL}/api/ventas/analisis${query}`);
  const data = await respuesta.json();
  if (!data.success) throw new Error(data.error || 'No se pudo obtener el análisis de ventas.');
  return data;
}

export async function cargarArchivoInicial(tipoReporte, archivo, sucursal) {
  const formData = new FormData();
  formData.append('tipo_reporte', tipoReporte);
  formData.append('archivo', archivo);
  if (sucursal) formData.append('sucursal', sucursal);

  const respuesta = await fetch(`${API_URL}/api/carga_inicial`, {
    method: 'POST',
    body: formData,
  });

  try {
    return await respuesta.json();
  } catch {
    return { success: false, error: `Respuesta inválida del servidor (HTTP ${respuesta.status}).` };
  }
}
