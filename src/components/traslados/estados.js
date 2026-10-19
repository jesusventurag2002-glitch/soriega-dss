import {
  CheckCircle2, CircleDashed, Clock, FileEdit, PackageCheck, PackageX, Truck, Archive, Ban, AlertTriangle,
} from 'lucide-react';

// Presentación de cada estado: color con significado fijo (ámbar = espera, azul = en curso,
// verde = completado, rojo = rechazo/incidencia, gris = inactivo) + icono + texto.
export const ESTADOS = {
  borrador: { texto: 'Borrador', icono: FileEdit, clase: 'bg-slate-100 text-slate-700 ring-slate-200' },
  pendiente_aprobacion: { texto: 'Pendiente de aprobación', icono: Clock, clase: 'bg-amber-50 text-amber-800 ring-amber-200' },
  aprobado: { texto: 'Aprobado', icono: CheckCircle2, clase: 'bg-sky-50 text-sky-800 ring-sky-200' },
  despachado: { texto: 'Despachado', icono: Truck, clase: 'bg-indigo-50 text-indigo-800 ring-indigo-200' },
  recibido: { texto: 'Recibido', icono: PackageCheck, clase: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  recibido_con_diferencias: { texto: 'Recibido con diferencias', icono: AlertTriangle, clase: 'bg-red-50 text-red-800 ring-red-200' },
  cerrado: { texto: 'Cerrado', icono: Archive, clase: 'bg-emerald-100 text-emerald-900 ring-emerald-300' },
  rechazado: { texto: 'Rechazado', icono: Ban, clase: 'bg-red-50 text-red-700 ring-red-200' },
  descartado: { texto: 'Descartado', icono: PackageX, clase: 'bg-slate-50 text-slate-500 ring-slate-200' },
};

export const ESTADO_DESCONOCIDO = { texto: 'Desconocido', icono: CircleDashed, clase: 'bg-slate-50 text-slate-500 ring-slate-200' };

// Pestañas de la bandeja (coinciden con GRUPOS_ESTADO del backend).
export const GRUPOS = [
  { id: 'activos', texto: 'Activos' },
  { id: 'borradores', texto: 'Borradores' },
  { id: 'por_aprobar', texto: 'Por aprobar' },
  { id: 'por_despachar', texto: 'Por despachar' },
  { id: 'en_transito', texto: 'En tránsito' },
  { id: 'por_cerrar', texto: 'Por cerrar' },
  { id: 'cerrados', texto: 'Cerrados' },
  { id: 'rechazados', texto: 'Descartados' },
];

// Pestaña en la que queda cada estado, para decirle al usuario dónde encontrar el registro tras una acción.
export const GRUPO_DE_ESTADO = {
  borrador: 'Borradores',
  pendiente_aprobacion: 'Por aprobar',
  aprobado: 'Por despachar',
  despachado: 'En tránsito',
  recibido: 'Por cerrar',
  recibido_con_diferencias: 'Por cerrar',
  cerrado: 'Cerrados',
  rechazado: 'Descartados',
  descartado: 'Descartados',
};

export const SIGUIENTE_PASO = {
  borrador: 'Revisa los artículos y sus cantidades, y envía el documento a aprobación.',
  pendiente_aprobacion: 'Un gerente debe aprobarlo o rechazarlo.',
  aprobado: 'Registra el despacho cuando la mercancía salga del origen.',
  despachado: 'Registra la recepción cuando llegue al destino.',
  recibido: 'Un gerente debe cerrarlo para darlo por conciliado.',
  recibido_con_diferencias: 'Un gerente debe revisar la diferencia y cerrarlo.',
  cerrado: 'Operación finalizada.',
  rechazado: 'No requiere más acciones.',
  descartado: 'No requiere más acciones.',
};

export const MENSAJE_ACCION = {
  enviar: 'enviado a aprobación',
  descartar: 'descartado',
  aprobar: 'aprobado',
  rechazar: 'rechazado',
  despachar: 'despachado',
  recibir: 'recibido',
  cerrar: 'cerrado',
};

export const EVENTOS = {
  creado: 'Documento creado',
  articulos_agregados: 'Artículos agregados',
  articulo_retirado: 'Artículo retirado',
  cantidad_modificada: 'Cantidades modificadas',
  observaciones: 'Observaciones actualizadas',
  enviado_aprobacion: 'Enviado a aprobación',
  aprobado: 'Aprobado',
  rechazado: 'Rechazado',
  descartado: 'Descartado',
  despachado: 'Despacho registrado',
  recibido: 'Recepción registrada',
  recibido_con_diferencias: 'Recepción con diferencias',
  cerrado: 'Cerrado y conciliado',
};

export const CAMPOS = {
  cantidad_sugerida: 'Cantidad sugerida',
  cantidad_aprobada: 'Cantidad aprobada',
  cantidad_despachada: 'Cantidad despachada',
  cantidad_recibida: 'Cantidad recibida',
  diferencia: 'Diferencia',
  stock_origen: 'Stock en origen',
  stock_destino: 'Stock en destino',
  cobertura_dias: 'Cobertura del destino (días)',
  observaciones: 'Observaciones',
  articulos: 'Artículos',
  unidades: 'Unidades',
  unidades_aprobadas: 'Unidades aprobadas',
  unidades_despachadas: 'Unidades despachadas',
  unidades_recibidas: 'Unidades recibidas',
};

export const folioDe = (id) => `TR-${String(id).padStart(5, '0')}`;

// Cantidad relevante en cada etapa del ciclo (por artículo).
export function cantidadVigente(t) {
  if (t.cantidad_recibida != null) return { valor: t.cantidad_recibida, etiqueta: 'recibida' };
  if (t.cantidad_despachada != null) return { valor: t.cantidad_despachada, etiqueta: 'despachada' };
  if (t.cantidad_aprobada != null) return { valor: t.cantidad_aprobada, etiqueta: 'aprobada' };
  return { valor: t.cantidad_sugerida, etiqueta: 'sugerida' };
}

export const fechaHora = (iso) =>
  new Date(iso).toLocaleString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
