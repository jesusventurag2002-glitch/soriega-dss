import {
  LayoutDashboard, ArrowLeftRight, BarChart3, AlertOctagon, Database, Users, ClipboardX, Megaphone, Tag, Truck,
} from 'lucide-react';

const PISO_VENTA = ['consultar_stock', 'consultar_precios', 'recibir_mercancia', 'reportar_discrepancias', 'ver_promociones'];

// Permisos de cada rol. La interfaz solo consulta permisos, nunca el nombre del rol, para que cambiar
// lo que ve un rol sea editar esta tabla.
export const ROLES = {
  root: {
    etiqueta: 'Administrador del sistema',
    permisos: ['carga_datos', 'usuarios'],
  },
  procura_compras: {
    etiqueta: 'Procura y Compras',
    permisos: ['inicio', 'traslados', 'ventas', 'estancado', 'crear_promociones', 'revisar_discrepancias'],
  },
  gerente: {
    etiqueta: 'Gerente',
    permisos: ['inicio', 'traslados', 'ventas', 'estancado', 'crear_promociones', 'revisar_discrepancias'],
  },
  piso_venta: {
    etiqueta: 'Piso de venta',
    permisos: PISO_VENTA,
  },
  embalador: {
    etiqueta: 'Embalador (almacén)',
    permisos: [...PISO_VENTA, 'despachar_mercancia'],
  },
};

export const puede = (usuario, permiso) => !!usuario && !!ROLES[usuario.rol]?.permisos.includes(permiso);

// Vistas del menú en orden; cada una exige un permiso (o cualquiera de los indicados).
// La primera vista permitida es la que se abre al iniciar sesión.
export const VISTAS = [
  { id: 'consulta', texto: 'Precios y stock', icono: Tag, permisos: ['consultar_precios', 'consultar_stock'] },
  { id: 'inicio', texto: 'Inicio', icono: LayoutDashboard, permisos: ['inicio'] },
  { id: 'logistica', texto: 'Despacho y recepción', icono: Truck, permisos: ['despachar_mercancia', 'recibir_mercancia'] },
  { id: 'traslados', texto: 'Traslados', icono: ArrowLeftRight, permisos: ['traslados'] },
  { id: 'ventas', texto: 'Análisis de ventas', icono: BarChart3, permisos: ['ventas'] },
  { id: 'estancado', texto: 'Capital estancado', icono: AlertOctagon, permisos: ['estancado'] },
  { id: 'discrepancias', texto: 'Discrepancias', icono: ClipboardX, permisos: ['reportar_discrepancias', 'revisar_discrepancias'] },
  { id: 'promociones', texto: 'Promociones', icono: Megaphone, permisos: ['ver_promociones'] },
  { id: 'configuracion', texto: 'Carga de datos', icono: Database, permisos: ['carga_datos'] },
  { id: 'usuarios', texto: 'Usuarios', icono: Users, permisos: ['usuarios'] },
];

export const vistasPermitidas = (usuario) => VISTAS.filter((v) => v.permisos.some((p) => puede(usuario, p)));
export const puedeVer = (usuario, vista) => vistasPermitidas(usuario).some((v) => v.id === vista);
export const vistaInicial = (usuario) => vistasPermitidas(usuario)[0]?.id ?? null;
