# AGENTS.md — Soriega DSS

Sistema de apoyo a decisiones para el inventario de una cadena de tiendas (traslados, ventas, capital estancado, discrepancias, promociones). Detalle funcional en `README.md` y `docs/logica-backend.md`.

## Stack

- **Frontend** (`src/`): React 18 + Vite 6 + Tailwind CSS 4, iconos `lucide-react`, gráficos `recharts`. Pruebas con Vitest + Testing Library (jsdom).
- **Backend** (`backend/`): Flask + SQLAlchemy sobre PostgreSQL (`dss_inventario`). Arquitectura hexagonal.

## Comandos

```bash
npm install && npm run dev          # frontend en http://localhost:5173 (proxy /api -> 127.0.0.1:5000)
npm test                            # Vitest
npm run build                       # build de producción en dist/
cd backend && pip install -r requirements-dev.txt
cd backend && python app.py         # requiere DATABASE_URL
cd backend && python -m pytest -q   # pruebas backend
```

CI (`.github/workflows/tests.yml`) ejecuta `pytest` (Python 3.14) y `npm test` (Node 24) en cada PR. Ambos deben pasar.

## Arquitectura del backend (respetarla)

- `dominio/`: reglas de negocio puras. Sin Flask, sin SQLAlchemy, sin E/S.
- `aplicacion/`: casos de uso (`Casos*`) que orquestan el dominio a través de puertos.
- `puertos/`: interfaces `Protocol` que necesita el dominio.
- `adaptadores/entrada/`: blueprints Flask bajo `/api`.
- `adaptadores/salida/`: repositorios SQLAlchemy, lector de Excel, migraciones del esquema.
- `app.py`: solo composición. No poner lógica aquí.

Una regla de negocio nueva va en `dominio/` con su prueba en `backend/tests/`. Los errores de dominio usan `ErrorDominio`, `Prohibido` y `NoEncontrado`; las rutas los traducen a HTTP.

## Frontend

- Reutilizar los componentes de `src/components/ui/` (`Boton`, `Dialogo`, `Aviso`, `Encabezado`, `EstadoVacio`, `PanelLateral`) antes de crear otros.
- Formato de montos con `src/utils/` (`usd`, `bs`, `usdCompacto`).
- Llamadas a la API desde `src/services/`; los errores llegan como `ErrorApi`.
- Roles y vistas en `src/auth/roles.js`; usuarios de demostración en `src/auth/usuarios.js` (no es seguridad real; no tratarla como tal).

## Convenciones

- Código, nombres, comentarios, commits y documentación en **español**.
- Cambios mínimos y completos: no añadir dependencias, abstracciones ni opciones que nadie pidió.
- Comentar solo el *porqué* que el código no muestra.
- Ramas por tema (`docs/…`, `seguridad/…`, `ci/…`) y PR hacia `main`. No hacer commit directo en `main`.

## Seguridad y datos

- Nunca commitear `.env`, credenciales ni archivos de `MUESTRAS/`/`muestras/` (datos reales del negocio).
- No exponer errores internos en respuestas HTTP. Validar y acotar los parámetros de entrada en las rutas.
