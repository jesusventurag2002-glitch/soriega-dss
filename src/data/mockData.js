// Datos simulados que aún no provienen del backend (login, alertas de auditoría y análisis de ventas).

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

// Ventas del mes actual por sucursal y grupo de producto (USD). El total de cada sucursal se deriva de sus grupos.
export const VENTAS_SUCURSALES = [
  {
    sucursal: 'Centro',
    grupos: [
      { grupo: 'Hogar', total: 18450 },
      { grupo: 'Automotriz', total: 9320 },
      { grupo: 'Eléctrico', total: 14780 },
      { grupo: 'Ferretería', total: 11240 },
    ],
  },
  {
    sucursal: 'Norte',
    grupos: [
      { grupo: 'Hogar', total: 12100 },
      { grupo: 'Automotriz', total: 15860 },
      { grupo: 'Eléctrico', total: 8930 },
      { grupo: 'Ferretería', total: 10470 },
    ],
  },
  {
    sucursal: 'Sur',
    grupos: [
      { grupo: 'Hogar', total: 9870 },
      { grupo: 'Automotriz', total: 6420 },
      { grupo: 'Eléctrico', total: 11350 },
      { grupo: 'Ferretería', total: 13980 },
    ],
  },
].map((s) => ({ ...s, total: s.grupos.reduce((suma, g) => suma + g.total, 0) }));

// Ventas diarias de las tres sucursales en los últimos 7 días, terminando hoy.
export const VENTAS_ULTIMOS_7_DIAS = [4820, 5310, 4975, 6120, 5890, 7240, 6680].map((total, i, arr) => {
  const fecha = new Date();
  fecha.setDate(fecha.getDate() - (arr.length - 1 - i));
  return { fecha, total };
});
