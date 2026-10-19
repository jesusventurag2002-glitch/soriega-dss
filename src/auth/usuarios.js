// Usuarios de demostración mientras no exista el backend de usuarios.
// Las contraseñas están en el código del frontend: cualquiera puede leerlas. Esto NO es seguridad real;
// solo sirve para probar los roles. Antes de producción, la validación debe hacerse en el servidor.
export const USUARIOS_DEMO = [
  { usuario: 'root', clave: '28691009', nombre: 'Administrador', rol: 'root' },
  { usuario: 'compras', clave: '123', nombre: 'María González', rol: 'procura_compras' },
  { usuario: 'gerente', clave: '123', nombre: 'Carlos Ramírez', rol: 'gerente' },
  { usuario: 'tienda01', clave: '123', nombre: 'Tienda Barcelona', rol: 'piso_venta', sucursal: 'Barcelona' },
  { usuario: 'almacen01', clave: '123', nombre: 'Embalador Almacén', rol: 'embalador', sucursal: 'Almacén Principal' },
];

// Datos del usuario que se pueden guardar y mostrar: nunca incluye la contraseña.
export const datosPublicos = ({ clave: _clave, ...resto }) => resto;
