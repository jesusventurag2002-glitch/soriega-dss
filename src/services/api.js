// Por defecto se usa la misma URL del frontend: el proxy de Vite reenvía /api al backend Flask,
// lo que permite abrir la app desde otros dispositivos de la red. Ajustable con VITE_API_URL en un .env.
const API_URL = import.meta.env.VITE_API_URL ?? '';

// Usuario del login simulado: se envía al backend para registrar quién ejecuta cada acción.
// No es autenticación real; el nombre va codificado porque las cabeceras no admiten acentos.
let usuarioActual = null;
export const establecerUsuario = (usuario) => {
  usuarioActual = usuario;
};

const cabecerasUsuario = () =>
  usuarioActual ? { 'X-Usuario': encodeURIComponent(usuarioActual.nombre), 'X-Rol': usuarioActual.rol } : {};

export class ErrorApi extends Error {
  constructor(mensaje, status, cuerpo) {
    super(mensaje);
    this.status = status;
    this.cuerpo = cuerpo;
  }
}

// Petición JSON común: un error del servidor nunca se presenta como éxito.
async function pedir(ruta, { metodo = 'GET', cuerpo, params } = {}) {
  const query = params
    ? new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)).toString()
    : '';
  let respuesta;
  try {
    respuesta = await fetch(`${API_URL}${ruta}${query ? `?${query}` : ''}`, {
      method: metodo,
      headers: {
        ...(cuerpo !== undefined && { 'Content-Type': 'application/json' }),
        ...cabecerasUsuario(),
      },
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ErrorApi('No se pudo conectar con el servidor. Verifica que el backend esté activo.', 0);
  }
  let data;
  try {
    data = await respuesta.json();
  } catch {
    throw new ErrorApi(`Respuesta inválida del servidor (HTTP ${respuesta.status}).`, respuesta.status);
  }
  if (!respuesta.ok || data.success === false) {
    throw new ErrorApi(data.error || `Error del servidor (HTTP ${respuesta.status}).`, respuesta.status, data);
  }
  return data;
}

// ---- Traslados ----
export const listarTraslados = (filtros) => pedir('/api/traslados', { params: filtros });
export const obtenerTraslado = (id) => pedir(`/api/traslados/${id}`).then((d) => d.traslado);
export const editarTraslado = (id, version, cambios) =>
  pedir(`/api/traslados/${id}`, { metodo: 'PATCH', cuerpo: { version, ...cambios } }).then((d) => d.traslado);
export const accionTraslado = (id, accion, version, extra = {}) =>
  pedir(`/api/traslados/${id}/acciones`, { metodo: 'POST', cuerpo: { accion, version, ...extra } }).then((d) => d.traslado);
export const generarTraslados = (dias, clases) => pedir('/api/traslados/generar', { metodo: 'POST', cuerpo: { dias, clases } });
export const retirarArticulo = (id, lineaId, version, comentario) =>
  pedir(`/api/traslados/${id}/lineas/${lineaId}`, { metodo: 'DELETE', cuerpo: { version, comentario } }).then((d) => d.traslado);
export const loteTraslados = (accion, items) => pedir('/api/traslados/lote', { metodo: 'POST', cuerpo: { accion, items } });
export const crearRetorno = (datos) => pedir('/api/traslados', { metodo: 'POST', cuerpo: datos }).then((d) => d.traslado);

// ---- Mercancía estancada ----
// Artículos con stock sin ventas en los últimos `diasMin` días, ordenados por capital inmovilizado.
// Sin sucursal, existencia consolidada (sucursales + almacén).
export const obtenerCapitalEstancado = (diasMin, sucursal, limite = 100) =>
  pedir('/api/capital_estancado', { params: { dias_min: diasMin, sucursal, limite } });

export const registrarAccionEstancado = (datos) =>
  pedir('/api/estancado/acciones', { metodo: 'POST', cuerpo: datos }).then((d) => d.accion);
export const cerrarAccionEstancado = (id, estado, resultado) =>
  pedir(`/api/estancado/acciones/${id}`, { metodo: 'PATCH', cuerpo: { estado, resultado } }).then((d) => d.accion);
export const listarAccionesEstancado = (estado, tipo) =>
  pedir('/api/estancado/acciones', { params: { estado, tipo } }).then((d) => d.acciones);

// ---- Piso de venta ----
export const consultarStock = (q) => pedir('/api/inventario/stock', { params: { q } }).then((d) => d.items);
export const listarDiscrepancias = (filtros) => pedir('/api/discrepancias', { params: filtros }).then((d) => d.discrepancias);
export const reportarDiscrepancia = (datos) =>
  pedir('/api/discrepancias', { metodo: 'POST', cuerpo: datos }).then((d) => d.discrepancia);
export const revisarDiscrepancia = (id, resolucion) =>
  pedir(`/api/discrepancias/${id}`, { metodo: 'PATCH', cuerpo: { resolucion } }).then((d) => d.discrepancia);

// ---- Centro de decisiones ----
export const obtenerDashboard = (sucursal) => pedir('/api/dashboard', { params: { sucursal } });
export const obtenerCriticos = (sucursal) => pedir('/api/inventario/criticos', { params: { sucursal } });
export const listarImportaciones = () => pedir('/api/importaciones').then((d) => d.importaciones);

// Ventas de un mes por sucursal y grupo. Sin periodo, el backend usa el mes de la última venta registrada.
// `excluir`: ids de excepciones a dejar fuera ([] = facturación bruta); sin indicarlo, las de la hoja ANAL.
export async function obtenerAnalisisVentas(periodo, excluir) {
  const params = new URLSearchParams();
  if (periodo) {
    params.set('mes', periodo.mes);
    params.set('ano', periodo.ano);
  }
  if (excluir) params.set('excluir', excluir.join(','));
  const query = params.toString() ? `?${params}` : '';
  const respuesta = await fetch(`${API_URL}/api/ventas/analisis${query}`);
  const data = await respuesta.json();
  if (!data.success) throw new Error(data.error || 'No se pudo obtener el análisis de ventas.');
  return data;
}

// Guarda qué excepciones se excluyen de la facturación (null = volver a las de la hoja ANAL).
export async function guardarExcepciones(excluir) {
  const respuesta = await fetch(`${API_URL}/api/excepciones`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(excluir ? { excluir } : { restablecer: true }),
  });
  const data = await respuesta.json();
  if (!data.success) throw new Error(data.error || 'No se pudieron guardar las excepciones.');
  return data;
}

// Tasas BCV e interna vigentes en `fecha` (ISO, por defecto hoy) y su historial.
export async function obtenerTasas(fecha, dias = 15) {
  const params = new URLSearchParams({ dias });
  if (fecha) params.set('fecha', fecha);
  const respuesta = await fetch(`${API_URL}/api/tasas?${params}`);
  const data = await respuesta.json();
  if (!data.success) throw new Error(data.error || 'No se pudieron obtener las tasas.');
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
    headers: cabecerasUsuario(), // para registrar quién importó el archivo
  });

  try {
    return await respuesta.json();
  } catch {
    return { success: false, error: `Respuesta inválida del servidor (HTTP ${respuesta.status}).` };
  }
}
