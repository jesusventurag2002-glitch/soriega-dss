// Backend temporal en Python. Ajustable con VITE_API_URL en un archivo .env.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

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
