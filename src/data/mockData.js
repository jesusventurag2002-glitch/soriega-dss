// Datos simulados que aún no provienen del backend (login y alertas de auditoría).

export const USUARIOS = {
  analista: { nombre: 'María González', rol: 'analista', etiqueta: 'Analista de Inventario' },
  gerente: { nombre: 'Carlos Ramírez', rol: 'gerente', etiqueta: 'Gerente de Logística' },
};

export const ALERTAS = [
  {
    id: 1,
    tipo: 'discrepancia',
    titulo: '3 discrepancias de códigos',
    detalle: 'Códigos de barra distintos entre Sucursal Centro y Almacén Principal.',
    hace: 'Hace 12 min',
    leida: false,
  },
  {
    id: 2,
    tipo: 'quiebre',
    titulo: 'Riesgo de quiebre de stock',
    detalle: '2 productos clase A bajo el punto de reorden en Sucursal Norte.',
    hace: 'Hace 1 h',
    leida: false,
  },
  {
    id: 3,
    tipo: 'sync',
    titulo: 'Sincronización ODBC completada',
    detalle: 'Inventario de 4 sucursales actualizado desde el sistema administrativo.',
    hace: 'Hace 3 h',
    leida: true,
  },
];
