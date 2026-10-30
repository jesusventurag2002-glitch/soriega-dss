# Soriega DSS

Sistema de apoyo a decisiones para el inventario de una cadena de tiendas: carga de reportes de inventario y ventas, sugerencias de traslado entre almacén y sucursales, análisis de ventas, capital estancado, discrepancias y promociones.

- **Frontend:** React 18 + Vite + Tailwind CSS (`src/`)
- **Backend:** Flask + SQLAlchemy sobre PostgreSQL, en arquitectura hexagonal (`backend/`)
- **Documentación:** modelo de dominio y boceto de tesis (`docs/`)

## Requisitos

- Node.js 20+
- Python 3.10+
- PostgreSQL con una base `dss_inventario`

## Puesta en marcha

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
DATABASE_URL="postgresql+psycopg://<usuario>:<clave>@127.0.0.1:5432/dss_inventario" python app.py
```

Escucha en `http://127.0.0.1:5000`. Al arrancar crea las tablas y aplica las migraciones del esquema.

Variables de entorno:

| Variable | Uso | Por defecto |
|---|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL | `postgresql+psycopg://usuario:password@localhost:5432/dss_inventario` |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma | `http://localhost:5173,http://localhost:3000` |
| `PORT` | Puerto del backend | `5000` |
| `FLASK_DEBUG` | `1` activa el modo debug | — |

### Frontend

```bash
npm install
npm run dev
```

Abre `http://localhost:5173`. Vite reenvía `/api` al backend en `127.0.0.1:5000` y también es accesible desde otros dispositivos de la red local.

## Usuarios de demostración

Mientras no exista autenticación en el servidor, los usuarios están en `src/auth/usuarios.js` (no es seguridad real):

| Usuario | Rol |
|---|---|
| `root` | Administrador del sistema (carga de datos, usuarios) |
| `compras` | Procura y Compras |
| `gerente` | Gerente |
| `tienda01` | Piso de venta (Barcelona) |
| `almacen01` | Embalador (almacén) |

Los permisos de cada rol y las vistas que habilitan están en `src/auth/roles.js`.

## Estructura del backend

```
backend/
├── dominio/       reglas de negocio puras (traslados, demanda, ABC, discrepancias…)
├── aplicacion/    casos de uso que orquestan el dominio
├── puertos/       interfaces (Protocol) que el dominio necesita
├── adaptadores/
│   ├── entrada/   rutas Flask (blueprints) bajo /api
│   └── salida/    repositorios SQLAlchemy, lector de Excel, migraciones
├── tests/
└── app.py         solo composición: configura Flask y conecta adaptadores con casos de uso
```

## Pruebas

```bash
cd backend && python -m pytest   # backend
npm test                         # frontend (Vitest)
npm run build                    # compilación de producción en dist/
```
