import { useCallback, useEffect, useState } from 'react';
import {
  LayoutDashboard, Clock, Truck, PackageCheck, AlertTriangle, Flame, AlertOctagon, RefreshCw, ArrowRight,
  CheckCircle2, XCircle, Database, FileSpreadsheet, History,
} from 'lucide-react';
import Encabezado, { EstadoVacio } from './ui/Encabezado.jsx';
import Boton from './ui/Boton.jsx';
import Aviso from './ui/Aviso.jsx';
import PanelLateral from './ui/PanelLateral.jsx';
import { AbcBadge } from './Badges.jsx';
import WidgetVentas from './WidgetVentas.jsx';
import { EVENTOS, fechaHora } from './traslados/estados.js';
import { obtenerCriticos, obtenerDashboard } from '../services/api.js';
import { fechaLocal, usd } from '../utils/formato.js';

const TIPOS_REPORTE = { ventas: 'Ventas', inv_fisico: 'Inventario sucursal', inv_inval: 'Inventario almacén', tasas: 'Tasas internas' };
const fecha = (iso) => (iso ? fechaLocal(iso).toLocaleDateString('es-VE') : null);

// Tarjeta de indicador: siempre lleva a los registros que la componen.
function Indicador({ icono: Icono, acento, valor, etiqueta, detalle, onClick, alerta }) {
  return (
    <button
      onClick={onClick}
      className={`group flex flex-col items-start rounded-xl bg-white p-4 text-left ring-1 transition hover:shadow-md ${
        alerta ? 'ring-red-200' : 'ring-slate-200'
      }`}
    >
      <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${acento}`}>
        <Icono className="h-4.5 w-4.5" aria-hidden="true" />
      </span>
      <span className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{valor}</span>
      <span className="text-sm font-medium text-slate-700">{etiqueta}</span>
      <span className="mt-0.5 text-xs text-slate-500">{detalle}</span>
      <span className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 group-hover:text-slate-900">
        Ver registros <ArrowRight className="h-3 w-3" />
      </span>
    </button>
  );
}

function Bloque({ titulo, icono: Icono, accion, children }) {
  return (
    <section className="rounded-xl bg-white ring-1 ring-slate-200">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <h2 className="inline-flex items-center gap-2 font-semibold text-slate-900">
          {Icono && <Icono className="h-4 w-4 text-slate-400" />} {titulo}
        </h2>
        {accion}
      </div>
      <div className="divide-y divide-slate-100">{children}</div>
    </section>
  );
}

const articulosDe = (t) =>
  `${t.total_articulos} ${t.total_articulos === 1 ? 'artículo' : 'artículos'}: ${t.articulos.join(', ')}${
    t.total_articulos > t.articulos.length ? '…' : ''
  }`;

// Un documento de traslado pendiente: ruta, artículos que lleva y total de unidades.
function FilaTraslado({ t, onAbrir, extra }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <AbcBadge clase={t.clasificacion_abc} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-900">
          <span className="font-mono">{t.folio}</span> · {t.origen} → {t.destino}
        </p>
        <p className="truncate text-xs text-slate-500">
          {articulosDe(t)} · {t.total_unidades} u{extra}
        </p>
      </div>
      <Boton tamano="sm" onClick={() => onAbrir(t.id)}>
        Revisar
      </Boton>
    </div>
  );
}

function FilaCritico({ c, onAbrirTraslado }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <AbcBadge clase={c.clasificacion_abc} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-900">{c.nombre}</p>
        <p className="text-xs text-slate-500">
          {c.sucursal} · stock {c.stock} · vende {c.venta_diaria}/día ·{' '}
          <span className="font-semibold text-red-700">{c.cobertura_dias} días de cobertura</span> · almacén {c.stock_almacen}
        </p>
      </div>
      {c.traslado ? (
        <Boton tamano="sm" onClick={() => onAbrirTraslado(c.traslado.id)}>
          {c.traslado.folio}
        </Boton>
      ) : (
        <span className="whitespace-nowrap text-xs text-slate-400">{c.stock_almacen > 0 ? 'Sin traslado abierto' : 'Sin stock en almacén'}</span>
      )}
    </div>
  );
}

// Fechas de los datos: cuándo se importó cada archivo y hasta qué fecha llega su contenido.
function EstadoDatos({ datos, sucursal, onConfigurar }) {
  const sucursales = datos.sucursales.filter((s) => !sucursal || s.sucursal === sucursal);
  const incompletas = sucursales
    .map((s) => ({ s: s.sucursal, falta: [!s.inventario.cargado && 'inventario', !s.ventas.cargado && 'ventas'].filter(Boolean) }))
    .filter((x) => x.falta.length);
  const importado = (x) => (x?.importado_en ? `importado ${fechaHora(x.importado_en)}` : 'fecha de importación no registrada');

  return (
    <div className="space-y-2">
      {incompletas.length > 0 && (
        <Aviso
          tono="advertencia"
          titulo="Datos incompletos"
          accion={<Boton tamano="sm" onClick={onConfigurar}>Cargar archivos</Boton>}
        >
          {incompletas.map((x) => `${x.s}: falta ${x.falta.join(' y ')}`).join(' · ')}. Los indicadores que dependen de esa información no la
          incluyen.
        </Aviso>
      )}
      {!datos.almacen.cargado && (
        <Aviso tono="advertencia">No hay inventario del Almacén Principal cargado: no se pueden calcular traslados.</Aviso>
      )}
      <details className="rounded-xl bg-white px-4 py-3 text-sm ring-1 ring-slate-200">
        <summary className="cursor-pointer select-none font-medium text-slate-700">
          Origen de los datos <span className="font-normal text-slate-500">· archivos exportados, no información en tiempo real</span>
        </summary>
        <ul className="mt-2 space-y-1 text-xs text-slate-600">
          {sucursales.map((s) => (
            <li key={s.sucursal}>
              <strong>{s.sucursal}</strong> · ventas{' '}
              {s.ventas.cargado ? `hasta el ${fecha(s.ventas.datos_hasta)} (${importado(s.ventas)})` : 'no cargadas'} · inventario{' '}
              {s.inventario.cargado ? importado(s.inventario) : 'no cargado'}
            </li>
          ))}
          <li>
            <strong>Almacén Principal</strong> · inventario {datos.almacen.cargado ? importado(datos.almacen) : 'no cargado'}
          </li>
          <li>
            <strong>Tasas internas</strong> ·{' '}
            {datos.tasas.datos_hasta ? `registradas hasta el ${fecha(datos.tasas.datos_hasta)} (${importado(datos.tasas)})` : 'no cargadas'}
          </li>
          <li className="text-slate-400">
            Los reportes de inventario no indican su fecha de corte; se muestra la fecha de importación.
          </li>
        </ul>
      </details>
    </div>
  );
}

export default function CentroDecisiones({ usuario, sucursal, onSucursal, onIrTraslados, onAbrirTraslado, onIr }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [criticos, setCriticos] = useState(null); // panel con el listado completo

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setDatos(await obtenerDashboard(sucursal));
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, [sucursal]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const verCriticos = async () => {
    setCriticos({ cargando: true });
    try {
      setCriticos(await obtenerCriticos(sucursal));
    } catch (e) {
      setCriticos({ error: e.message });
    }
  };

  const filtroSucursal = sucursal ? { sucursal } : {};
  const t = datos?.traslados;
  const sinDatos = datos && datos.datos.sucursales.length === 0 && !datos.datos.almacen.cargado;
  const hayPendientes =
    datos && (datos.pendientes.por_aprobar.length || datos.criticos.total || datos.pendientes.con_diferencias.length ||
      datos.pendientes.en_transito.length || datos.acciones_estancado.pendientes);

  return (
    <div className="space-y-6">
      <Encabezado
        icono={LayoutDashboard}
        titulo="Centro de decisiones"
        subtitulo={`Hola, ${usuario.nombre.split(' ')[0]}. Qué requiere atención, dónde está y qué hacer.`}
      >
        <label className="sr-only" htmlFor="sucursal-contexto">
          Sucursal
        </label>
        <select
          id="sucursal-contexto"
          value={sucursal}
          onChange={(e) => onSucursal(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900"
        >
          <option value="">Todas las sucursales (consolidado)</option>
          {datos?.datos.sucursales.map((s) => (
            <option key={s.sucursal} value={s.sucursal}>
              {s.sucursal}
            </option>
          ))}
        </select>
        <Boton icono={RefreshCw} cargando={cargando && !!datos} onClick={cargar} aria-label="Actualizar indicadores">
          <span className="hidden sm:inline">Actualizar</span>
        </Boton>
      </Encabezado>

      {error && (
        <Aviso tono="error" titulo="No se pudo cargar el centro de decisiones" accion={<Boton tamano="sm" onClick={cargar}>Reintentar</Boton>}>
          {error}
        </Aviso>
      )}

      {!datos && !error && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-6" aria-label="Cargando indicadores">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-36 animate-pulse rounded-xl bg-slate-200/70" />
          ))}
        </div>
      )}

      {sinDatos && (
        <EstadoVacio icono={Database} titulo="Aún no hay datos cargados">
          Carga los inventarios y las ventas en Configuración inicial para calcular indicadores y alertas.
          <div className="mt-3">
            <Boton variante="primario" onClick={() => onIr('configuracion')}>
              Ir a Configuración inicial
            </Boton>
          </div>
        </EstadoVacio>
      )}

      {datos && !sinDatos && (
        <div className={`space-y-6 transition-opacity ${cargando ? 'opacity-60' : ''}`}>
          <EstadoDatos datos={datos.datos} sucursal={sucursal} onConfigurar={() => onIr('configuracion')} />

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Indicador
              icono={Clock}
              acento="bg-amber-50 text-amber-700"
              valor={t.por_aprobar}
              etiqueta="Por aprobar"
              detalle={t.por_aprobar ? 'Esperan decisión de un gerente' : 'Sin pendientes'}
              onClick={() => onIrTraslados({ grupo: 'por_aprobar', ...filtroSucursal })}
            />
            <Indicador
              icono={PackageCheck}
              acento="bg-sky-50 text-sky-700"
              valor={t.por_despachar}
              etiqueta="Por despachar"
              detalle="Aprobados sin salida registrada"
              onClick={() => onIrTraslados({ grupo: 'por_despachar', ...filtroSucursal })}
            />
            <Indicador
              icono={Truck}
              acento="bg-indigo-50 text-indigo-700"
              valor={t.en_transito}
              etiqueta="Por recibir"
              detalle="Despachados sin recepción"
              onClick={() => onIrTraslados({ grupo: 'en_transito', ...filtroSucursal })}
            />
            <Indicador
              icono={AlertTriangle}
              acento="bg-red-50 text-red-700"
              valor={t.con_diferencias}
              etiqueta="Con diferencias"
              detalle="Recepciones por conciliar"
              alerta={t.con_diferencias > 0}
              onClick={() => onIrTraslados({ grupo: 'por_cerrar', ...filtroSucursal })}
            />
            <Indicador
              icono={Flame}
              acento="bg-red-50 text-red-700"
              valor={datos.criticos.total}
              etiqueta="Productos críticos"
              detalle={`A y B con menos de ${datos.criticos.dias_cobertura} días de cobertura`}
              alerta={datos.criticos.total > 0}
              onClick={verCriticos}
            />
            <Indicador
              icono={AlertOctagon}
              acento="bg-slate-100 text-slate-700"
              valor={datos.capital_estancado ? usd(datos.capital_estancado.total, 0) : '—'}
              etiqueta="Capital estancado"
              detalle={
                datos.capital_estancado
                  ? `${datos.capital_estancado.articulos} artículos sin venta en ${datos.capital_estancado.dias_min}+ días${
                      datos.capital_estancado.consolidado ? ' · incluye almacén' : ''
                    }`
                  : 'Requiere ventas cargadas'
              }
              onClick={() => onIr('estancado')}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-2">
              {!hayPendientes && <Aviso tono="exito" titulo="Nada requiere atención en esta vista" />}

              {datos.pendientes.por_aprobar.length > 0 && (
                <Bloque
                  titulo="Propuestas por aprobar"
                  icono={Clock}
                  accion={
                    <Boton tamano="sm" variante="fantasma" onClick={() => onIrTraslados({ grupo: 'por_aprobar', ...filtroSucursal })}>
                      Ver las {t.por_aprobar}
                    </Boton>
                  }
                >
                  {datos.pendientes.por_aprobar.map((x) => (
                    <FilaTraslado key={x.id} t={x} onAbrir={onAbrirTraslado} />
                  ))}
                </Bloque>
              )}

              {datos.criticos.total > 0 && (
                <Bloque
                  titulo="Productos en riesgo de agotamiento"
                  icono={Flame}
                  accion={
                    <Boton tamano="sm" variante="fantasma" onClick={verCriticos}>
                      Ver los {datos.criticos.total}
                    </Boton>
                  }
                >
                  {datos.criticos.items.map((c) => (
                    <FilaCritico key={`${c.codigo}-${c.sucursal}`} c={c} onAbrirTraslado={onAbrirTraslado} />
                  ))}
                </Bloque>
              )}

              {(datos.pendientes.con_diferencias.length > 0 || datos.pendientes.en_transito.length > 0) && (
                <Bloque titulo="Recepciones pendientes e incidencias" icono={Truck}>
                  {datos.pendientes.con_diferencias.map((x) => (
                    <FilaTraslado
                      key={x.id}
                      t={x}
                      onAbrir={onAbrirTraslado}
                      extra={<span className="font-semibold text-red-700"> · {x.con_diferencias} con diferencia</span>}
                    />
                  ))}
                  {datos.pendientes.en_transito.map((x) => (
                    <FilaTraslado key={x.id} t={x} onAbrir={onAbrirTraslado} extra={` · en tránsito desde ${fechaHora(x.actualizado_en)}`} />
                  ))}
                </Bloque>
              )}

              {datos.acciones_estancado.pendientes > 0 && (
                <Bloque
                  titulo="Acciones sobre mercancía estancada en curso"
                  icono={AlertOctagon}
                  accion={
                    <Boton tamano="sm" variante="fantasma" onClick={() => onIr('estancado')}>
                      Ir al módulo
                    </Boton>
                  }
                >
                  {datos.acciones_estancado.items.map((a) => (
                    <div key={a.id} className="px-4 py-3 text-sm">
                      <p className="font-medium text-slate-900">{a.articulo_nombre}</p>
                      <p className="text-xs text-slate-500">
                        {a.tipo_etiqueta} · registrada por {a.creado_por} el {fechaHora(a.creado_en)}
                      </p>
                    </div>
                  ))}
                </Bloque>
              )}
            </div>

            <div className="space-y-4">
              <Bloque titulo="Actividad reciente" icono={History}>
                {datos.actividad.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-400">Sin movimientos todavía.</p>}
                {datos.actividad.map((e) => (
                  <button
                    key={e.id}
                    onClick={() => onAbrirTraslado(e.traslado.id)}
                    className="block w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50"
                  >
                    <p className="text-slate-900">
                      <span className={e.tipo === 'rechazado' || e.tipo === 'recibido_con_diferencias' ? 'font-medium text-red-700' : 'font-medium'}>
                        {EVENTOS[e.tipo] ?? e.tipo}
                      </span>{' '}
                      · <span className="font-mono text-xs">{e.traslado.folio}</span>
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {e.traslado.origen} → {e.traslado.destino} · {articulosDe(e.traslado)}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {e.usuario} · {fechaHora(e.fecha)}
                    </p>
                  </button>
                ))}
              </Bloque>

              <Bloque titulo="Importaciones recientes" icono={FileSpreadsheet}>
                {datos.importaciones.length === 0 && (
                  <p className="px-4 py-6 text-center text-sm text-slate-400">Sin importaciones registradas.</p>
                )}
                {datos.importaciones.map((i) => (
                  <div key={i.id} className="flex items-start gap-2 px-4 py-2.5 text-sm">
                    {i.exito ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="Correcta" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" aria-label="Con error" />
                    )}
                    <div className="min-w-0">
                      <p className="text-slate-900">
                        {TIPOS_REPORTE[i.tipo_reporte] ?? i.tipo_reporte}
                        {i.sucursal && ` · ${i.sucursal}`}
                      </p>
                      <p className="truncate text-xs text-slate-500" title={i.mensaje}>
                        {i.archivo} · {fechaHora(i.fecha_importacion)}
                        {i.datos_hasta && ` · datos hasta ${fecha(i.datos_hasta)}`}
                      </p>
                    </div>
                  </div>
                ))}
              </Bloque>
            </div>
          </div>

          <WidgetVentas onVerDesglose={() => onIr('ventas')} />
        </div>
      )}

      <PanelLateral
        abierto={criticos != null}
        titulo="Productos en riesgo de agotamiento"
        subtitulo={`${sucursal || 'Todas las sucursales'} · clases A y B con menos de ${datos?.criticos.dias_cobertura ?? 7} días de cobertura`}
        onCerrar={() => setCriticos(null)}
      >
        {criticos?.cargando && <div className="m-5 h-40 animate-pulse rounded-xl bg-slate-100" />}
        {criticos?.error && <Aviso tono="error" className="m-5">{criticos.error}</Aviso>}
        {criticos?.items && (
          <div className="divide-y divide-slate-100">
            {criticos.items.length === 0 && <p className="p-6 text-center text-sm text-slate-500">No hay productos críticos.</p>}
            {criticos.items.map((c) => (
              <FilaCritico
                key={`${c.codigo}-${c.sucursal}`}
                c={c}
                onAbrirTraslado={(id) => {
                  setCriticos(null);
                  onAbrirTraslado(id);
                }}
              />
            ))}
            <p className="px-4 py-3 text-xs text-slate-400">
              Cobertura = existencia en la sucursal ÷ venta diaria (ventas comerciales). Para reponer los que no tienen traslado
              abierto, usa «Generar propuestas» en Traslados.
            </p>
          </div>
        )}
      </PanelLateral>
    </div>
  );
}

