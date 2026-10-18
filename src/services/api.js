// Backend temporal en Python. Ajustable con VITE_API_URL en un archivo .env.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

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
        ORDEN_ABC[a.clasificacion_abc] - ORDEN_ABC[b.clasificacion_abc] || b.cantidad_sugerida - a.cantidad_sugerida
    );
}

export async function cargarArchivoInicial(tipoReporte, archivo) {
  const formData = new FormData();
  formData.append('tipo_reporte', tipoReporte);
  formData.append('archivo', archivo);

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
