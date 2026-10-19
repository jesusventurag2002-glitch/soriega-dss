import { useCallback, useEffect, useState } from 'react';
import {
  AlertOctagon, DollarSign, PackageX, Hourglass, Tag, Warehouse, Truck, TrendingDown, RefreshCw, CheckCircle2, Ban,
  ArrowLeftRight,
} from 'lucide-react';
import Encabezado, { EstadoVacio } from './ui/Encabezado.jsx';
import Boton from './ui/Boton.jsx';
import Aviso from './ui/Aviso.jsx';
import Dialogo from './ui/Dialogo.jsx';
import { useAvisos } from './ui/Avisos.jsx';
import { ESTADOS, fechaHora } from './traslados/estados.js';
import {
  cerrarAccionEstancado, crearRetorno, listarAccionesEstancado, obtenerCapitalEstancado, registrarAccionEstancado,
} from '../services/api.js';
import { usd } from '../utils/formato.js';

const UMBRALES = [60, 90, 180];
const TIPOS = { promocion: 'Descuento / promoción', devolucion_proveedor: 'Devolución a proveedor' };

const fecha = (iso) => iso.split('-').reverse().join('/');

// El historial cubre menos de un año, así que "crítico" = sin ninguna venta registrada.
const severidad = (a) =>
  a.sin_ventas
    ? { texto: 'Sin ventas', clase: 'bg-red-600 text-white' }
    : a.dias_sin_vender >= 180
      ? { texto: 'Alto', clase: 'bg-amber-500 text-white' }
      : { texto: 'Moderado', clase: 'bg-amber-100 text-amber-800' };

const ESTADO_ACCION = {
  pendiente: { texto: 'En curso', clase: 'bg-amber-50 text-amber-800 ring-amber-200' },
  completada: { texto: 'Completada', clase: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  descartada: { texto: 'Descartada', clase: 'bg-slate-50 text-slate-500 ring-slate-200' },
};

function Kpi({ icono: Icono, etiqueta, valor, detalle, tono }) {
  const tonos = {
    rojo: 'bg-red-600 text-white ring-red-700',
    ambar: 'bg-amber-50 text-amber-900 ring-amber-200',
    neutro: 'bg-white text-slate-900 ring-slate-200',
  };
  return (
    <div className={`rounded-xl p-4 ring-1 ${tonos[tono]}`}>
      <div className="flex items-center gap-2 text-sm font-medium opacity-90">
        <Icono className="h-4 w-4" /> {etiqueta}
      </div>
      <p className="mt-2 truncate text-2xl font-bold tracking-tight sm:text-3xl">{valor}</p>
      {detalle && <p className="mt-1 truncate text-xs opacity-80">{detalle}</p>}
    </div>
  );
}

function DiasSinVender({ articulo }) {
  const { texto, clase } = severidad(articulo);
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="font-semibold text-slate-900">
        {articulo.sin_ventas ? '+' : ''}
        {articulo.dias_sin_vender} d
      </span>
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${clase}`}>{texto}</span>
    </div>
  );
}

function Ubicacion({ articulo }) {
  const sucursales = Object.entries(articulo.existencia_por_sucursal ?? {});
  return (
    <span className="text-xs text-slate-500">
      {sucursales.map(([nombre, cantidad]) => (
        <span key={nombre} className="whitespace-nowrap">
          {nombre} {cantidad} ·{' '}
        </span>
      ))}
      <span className="whitespace-nowrap">Alm. {articulo.existencia_almacen}</span>
    </span>
  );
}

// Barra con el peso del artículo sobre el capital inmovilizado total.
function ParticipacionCapital({ capital, total }) {
  const pct = total ? (capital / total) * 100 : 0;
  return (
    <div>
      <p className="font-semibold text-red-700">{usd(capital)}</p>
      <div className="mt-1 flex items-center gap-2">
        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-red-500" style={{ width: `${Math.max(pct, 1)}%` }} />
        </div>
        <span className="text-[11px] text-slate-500">{pct.toFixed(1)}%</span>
      </div>
    </div>
  );
}

// Qué se decidió sobre el artículo: retornos en curso y acciones registradas con su responsable.
function Seguimiento({ articulo, onAbrirTraslado, onCerrarAccion }) {
  if (!articulo.retornos.length && !articulo.acciones.length) {
    return <span className="text-xs text-slate-400">Sin decisión registrada</span>;
  }
  return (
    <ul className="space-y-1.5">
      {articulo.retornos.map((r) => (
        <li key={r.id}>
          <button onClick={() => onAbrirTraslado(r.id)} className="text-left text-xs text-slate-700 underline-offset-2 hover:underline">
            <span className="font-mono font-semibold">{r.folio}</span> · retorno desde {r.origen} ({r.cantidad} u) ·{' '}
            {ESTADOS[r.estado]?.texto ?? r.estado}
          </button>
        </li>
      ))}
      {articulo.acciones.slice(0, 2).map((a) => (
        <li key={a.id} className="text-xs text-slate-600">
          <span className={`mr-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1 ${ESTADO_ACCION[a.estado].clase}`}>
            {ESTADO_ACCION[a.estado].texto}
          </span>
          {a.tipo_etiqueta} · {a.creado_por} · {fechaHora(a.creado_en)}
          {a.resultado && <span className="block text-slate-500">Resultado: {a.resultado}</span>}
          {a.estado === 'pendiente' && (
            <span className="mt-1 flex gap-1.5">
              <Boton tamano="sm" icono={CheckCircle2} onClick={() => onCerrarAccion(articulo, a, 'completada')}>
                Registrar resultado
              </Boton>
              <Boton tamano="sm" variante="fantasma" onClick={() => onCerrarAccion(articulo, a, 'descartada')}>
                Descartar
              </Boton>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

// Sucursales con existencia que todavía no tienen un retorno abierto de este artículo.
const sucursalesParaRetorno = (articulo) =>
  Object.entries(articulo.existencia_por_sucursal ?? {}).filter(([s]) => !articulo.retornos.some((r) => r.origen === s));

function Acciones({ articulo, onAccion, compacto = false }) {
  const pendiente = (tipo) => articulo.acciones.some((a) => a.tipo === tipo && a.estado === 'pendiente');
  const disponiblesRetorno = sucursalesParaRetorno(articulo);
  const opciones = [
    {
      id: 'promocion', texto: 'Sugerir descuento / promoción', corto: 'Promoción', icono: Tag,
      deshabilitado: pendiente('promocion') && 'Ya hay una promoción en curso',
    },
    {
      id: 'retorno', texto: 'Retornar a Almacén Principal', corto: 'Al almacén', icono: Warehouse,
      // Solo se puede retornar al almacén lo que está en una sucursal, y sin duplicar un retorno en curso.
      deshabilitado:
        (articulo.existencia_sucursal === 0 && 'Sin existencia en sucursales') ||
        (disponiblesRetorno.length === 0 && 'Ya hay un retorno en curso desde cada sucursal con existencia'),
    },
    {
      id: 'devolucion_proveedor', texto: 'Devolución a proveedor', corto: 'A proveedor', icono: Truck,
      deshabilitado: pendiente('devolucion_proveedor') && 'Ya hay una devolución en curso',
    },
  ];
  return (
    <div className={compacto ? 'flex flex-wrap gap-1.5' : 'grid grid-cols-1 gap-2 sm:grid-cols-3'}>
      {opciones.map((o) => (
        <Boton
          key={o.id}
          tamano="sm"
          icono={o.icono}
          disabled={!!o.deshabilitado}
          title={o.deshabilitado || o.texto}
          onClick={() => onAccion(o.id, articulo)}
        >
          {compacto ? o.corto : o.texto}
        </Boton>
      ))}
    </div>
  );
}

// Retorno al almacén: se elige la sucursal de origen y la cantidad; queda como borrador de traslado.
function DialogoRetorno({ articulo, onCancelar, onConfirmar }) {
  const sucursales = sucursalesParaRetorno(articulo);
  const [origen, setOrigen] = useState(sucursales[0][0]);
  const [cantidad, setCantidad] = useState(String(sucursales[0][1]));
  const [comentario, setComentario] = useState('');
  const [error, setError] = useState(null);
  const [errorCantidad, setErrorCantidad] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const maximo = articulo.existencia_por_sucursal[origen];

  const enviar = async (e) => {
    e.preventDefault();
    const n = Number(cantidad);
    if (!Number.isInteger(n) || n < 1 || n > maximo) {
      setErrorCantidad(`Indica un entero entre 1 y ${maximo}.`);
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await onConfirmar({ origen, cantidad: n, comentario });
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 sm:items-center sm:p-4" onClick={() => !enviando && onCancelar()}>
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-retorno"
        onSubmit={enviar}
        onClick={(e) => e.stopPropagation()}
        className="w-full space-y-4 rounded-t-2xl bg-white p-5 shadow-2xl sm:max-w-md sm:rounded-2xl"
      >
        <div>
          <h2 id="titulo-retorno" className="font-semibold text-slate-900">
            Retornar al Almacén Principal
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {articulo.descripcion}. Se creará un borrador de traslado que seguirá el flujo de aprobación, despacho y recepción.
          </p>
        </div>
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Sucursal de origen</span>
          <select
            value={origen}
            onChange={(e) => {
              setOrigen(e.target.value);
              setCantidad(String(articulo.existencia_por_sucursal[e.target.value]));
            }}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            {sucursales.map(([s, n]) => (
              <option key={s} value={s}>
                {s} ({n} u)
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Cantidad a retornar</span>
          <input
            type="number"
            min={1}
            max={maximo}
            value={cantidad}
            onChange={(e) => {
              setCantidad(e.target.value);
              setErrorCantidad(null);
            }}
            aria-invalid={!!errorCantidad}
            className={`mt-1 w-40 rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 ${
              errorCantidad ? 'border-red-400' : 'border-slate-300'
            }`}
          />
          {errorCantidad && <span className="mt-1 block text-xs text-red-700">{errorCantidad}</span>}
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-700">
            Comentario <span className="font-normal text-slate-400">(opcional)</span>
          </span>
          <textarea
            rows={2}
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
          />
        </label>
        {error && <Aviso tono="error">{error}</Aviso>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Boton onClick={onCancelar} disabled={enviando}>
            Cancelar
          </Boton>
          <Boton type="submit" variante="primario" icono={ArrowLeftRight} cargando={enviando}>
            Crear borrador de retorno
          </Boton>
        </div>
      </form>
    </div>
  );
}

export default function PanelCapitalEstancado({ sucursalInicial = '', onAbrirTraslado }) {
  const avisar = useAvisos();
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [diasMin, setDiasMin] = useState(90);
  const [sucursal, setSucursal] = useState(sucursalInicial);
  const [enCurso, setEnCurso] = useState([]);
  const [dialogo, setDialogo] = useState(null);
  const [retorno, setRetorno] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [d, pendientes] = await Promise.all([obtenerCapitalEstancado(diasMin, sucursal), listarAccionesEstancado('pendiente')]);
      setDatos(d);
      setEnCurso(pendientes);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, [diasMin, sucursal]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Actualiza solo el artículo afectado, sin recargar la tabla.
  const actualizarArticulo = (codigo, cambio) =>
    setDatos((d) => d && { ...d, articulos: d.articulos.map((a) => (a.codigo === codigo ? cambio(a) : a)) });

  const iniciarAccion = (tipo, articulo) => {
    if (tipo === 'retorno') {
      setRetorno(articulo);
      return;
    }
    setDialogo({
      titulo: TIPOS[tipo],
      texto: `${articulo.descripcion} · ${usd(articulo.capital_estancado)} inmovilizados. Quedará registrado como acción en curso con tu nombre.`,
      textoConfirmar: 'Registrar acción',
      campo: { etiqueta: 'Detalle de la acción', requerido: false, placeholder: tipo === 'promocion' ? 'Ej.: 20% de descuento por 2 semanas' : 'Ej.: proveedor acepta devolución' },
      accion: async (comentario) => {
        const nueva = await registrarAccionEstancado({ articulo_codigo: articulo.codigo, tipo, comentario, capital: articulo.capital_estancado });
        actualizarArticulo(articulo.codigo, (a) => ({ ...a, acciones: [nueva, ...a.acciones] }));
        setEnCurso((l) => [nueva, ...l]);
        avisar({ tono: 'exito', titulo: `${TIPOS[tipo]} registrada`, texto: 'Cuando termine, registra el resultado desde la columna Seguimiento.' });
      },
    });
  };

  const cerrarAccion = (articulo, accion, estado) =>
    setDialogo({
      titulo: estado === 'completada' ? 'Registrar resultado' : 'Descartar acción',
      texto: `${accion.tipo_etiqueta} · ${accion.articulo_nombre}`,
      textoConfirmar: estado === 'completada' ? 'Guardar resultado' : 'Descartar',
      variante: estado === 'completada' ? 'primario' : 'peligro',
      campo: {
        etiqueta: estado === 'completada' ? 'Resultado obtenido' : 'Motivo',
        requerido: estado === 'completada',
        placeholder: estado === 'completada' ? 'Ej.: se vendieron 12 unidades con descuento' : '',
      },
      accion: async (resultado) => {
        const cerrada = await cerrarAccionEstancado(accion.id, estado, resultado);
        if (articulo) actualizarArticulo(articulo.codigo, (a) => ({ ...a, acciones: a.acciones.map((x) => (x.id === cerrada.id ? cerrada : x)) }));
        setEnCurso((l) => l.filter((x) => x.id !== cerrada.id));
        avisar({ tono: 'exito', titulo: estado === 'completada' ? 'Resultado registrado' : 'Acción descartada' });
      },
    });

  const resumen = datos?.resumen;
  const articulos = datos?.articulos ?? [];
  const mayor = articulos[0];
  const claseSelect = 'rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900';

  return (
    <div className="space-y-6">
      <Encabezado
        icono={AlertOctagon}
        tono="bg-red-600"
        titulo="Capital estancado"
        subtitulo={`Artículos sin venta que inmovilizan capital y requieren una decisión${datos ? ` · corte al ${fecha(datos.fecha_corte)}` : ''}`}
      >
        <label className="sr-only" htmlFor="sucursal-estancado">
          Ubicación
        </label>
        <select id="sucursal-estancado" value={sucursal} onChange={(e) => setSucursal(e.target.value)} className={claseSelect}>
          <option value="">Todas (sucursales + almacén)</option>
          {(datos?.sucursales ?? []).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
          <option value="Almacén Principal">Almacén Principal</option>
        </select>
        <label className="sr-only" htmlFor="umbral">
          Días sin ventas
        </label>
        <select id="umbral" value={diasMin} onChange={(e) => setDiasMin(Number(e.target.value))} className={claseSelect}>
          {UMBRALES.map((d) => (
            <option key={d} value={d}>
              Sin ventas hace {d}+ días
            </option>
          ))}
        </select>
        <Boton icono={RefreshCw} cargando={cargando && !!datos} onClick={cargar} aria-label="Recalcular" />
      </Encabezado>

      {error ? (
        <Aviso tono="error" titulo="No se pudo calcular el capital estancado" accion={<Boton tamano="sm" onClick={cargar}>Reintentar</Boton>}>
          {error}
        </Aviso>
      ) : (
        <div className="flex items-start gap-3 rounded-xl border-l-4 border-red-600 bg-red-50 p-4 ring-1 ring-red-200">
          <TrendingDown className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <p className="text-sm text-red-900">
            <span className="font-semibold">Atención requerida.</span> Estos artículos se separan de la clasificación ABC para no
            ocultar a los de alta rotación.{' '}
            {resumen && (
              <>
                Cada día sin decisión mantiene <span className="font-semibold">{usd(resumen.capital_total)}</span> fuera del flujo de
                caja{sucursal ? ` en ${sucursal}` : ''}.
              </>
            )}
          </p>
        </div>
      )}

      {enCurso.length > 0 && (
        <details className="rounded-xl bg-white px-4 py-3 ring-1 ring-slate-200" open>
          <summary className="cursor-pointer select-none text-sm font-semibold text-slate-900">
            Acciones en curso ({enCurso.length})
          </summary>
          <ul className="mt-2 divide-y divide-slate-100">
            {enCurso.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span className="min-w-0">
                  <span className="font-medium text-slate-900">{a.articulo_nombre}</span>
                  <span className="block text-xs text-slate-500">
                    {a.tipo_etiqueta} · {a.creado_por} · {fechaHora(a.creado_en)}
                    {a.comentario && ` · ${a.comentario}`}
                  </span>
                </span>
                <span className="flex gap-1.5">
                  <Boton tamano="sm" icono={CheckCircle2} onClick={() => cerrarAccion(articulos.find((x) => x.codigo === a.articulo_codigo), a, 'completada')}>
                    Registrar resultado
                  </Boton>
                  <Boton tamano="sm" variante="fantasma" icono={Ban} onClick={() => cerrarAccion(articulos.find((x) => x.codigo === a.articulo_codigo), a, 'descartada')}>
                    Descartar
                  </Boton>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {!datos && !error && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-slate-200/70" />
          ))}
        </div>
      )}

      {datos && (
        <div className={`space-y-6 transition-opacity ${cargando ? 'opacity-60' : ''}`}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi
              icono={DollarSign}
              etiqueta="Capital inmovilizado"
              valor={usd(resumen.capital_total)}
              tono="rojo"
              detalle={sucursal ? `Solo ${sucursal}` : 'Total consolidado: sucursales + almacén'}
            />
            <Kpi
              icono={PackageX}
              etiqueta="Artículos inactivos"
              valor={resumen.articulos.toLocaleString('es-VE')}
              tono="ambar"
              detalle={`${resumen.sin_ventas.toLocaleString('es-VE')} sin ventas en ${datos.dias_historial} días de historial`}
            />
            <Kpi icono={Hourglass} etiqueta="Promedio sin vender" valor={`${resumen.promedio_dias} días`} tono="ambar" />
            <Kpi icono={AlertOctagon} etiqueta="Mayor exposición" valor={mayor ? usd(mayor.capital_estancado) : '—'} tono="neutro" detalle={mayor?.descripcion} />
          </div>

          {articulos.length === 0 ? (
            <EstadoVacio icono={PackageX} titulo={`No hay artículos con más de ${diasMin} días sin ventas`}>
              {sucursal ? `en ${sucursal}.` : 'Prueba con un umbral menor.'}
            </EstadoVacio>
          ) : (
            <>
              <p className="text-xs text-slate-500">
                {articulos.length < resumen.articulos
                  ? `Mostrando los ${articulos.length} artículos con mayor capital de ${resumen.articulos.toLocaleString('es-VE')}, ordenados por importe.`
                  : 'Ordenados por capital inmovilizado, de mayor a menor.'}
              </p>

              {/* Escritorio (lg+) */}
              <div className="hidden overflow-x-auto rounded-xl bg-white ring-1 ring-slate-200 lg:block">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">#</th>
                      <th className="px-4 py-3">Artículo</th>
                      <th className="px-4 py-3 text-right">Existencia</th>
                      <th className="px-4 py-3 text-right">Costo unit.</th>
                      <th className="px-4 py-3">Sin vender</th>
                      <th className="px-4 py-3">Capital ↓</th>
                      <th className="px-4 py-3">Seguimiento</th>
                      <th className="px-4 py-3">Decisión</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {articulos.map((a, i) => (
                      <tr key={a.codigo} className="align-top transition hover:bg-red-50/40">
                        <td className="px-4 py-3 font-medium text-slate-400">{i + 1}</td>
                        <td className="max-w-[16rem] px-4 py-3">
                          <p className="font-medium text-slate-900">{a.descripcion}</p>
                          <p className="text-xs text-slate-400">
                            <span className="font-mono">{a.codigo}</span> · {a.grupo}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <p className="text-slate-700">{a.existencia}</p>
                          <Ubicacion articulo={a} />
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700">{usd(a.costo_unitario)}</td>
                        <td className="px-4 py-3">
                          <DiasSinVender articulo={a} />
                        </td>
                        <td className="px-4 py-3">
                          <ParticipacionCapital capital={a.capital_estancado} total={resumen.capital_total} />
                        </td>
                        <td className="max-w-[15rem] px-4 py-3">
                          <Seguimiento articulo={a} onAbrirTraslado={onAbrirTraslado} onCerrarAccion={cerrarAccion} />
                        </td>
                        <td className="px-4 py-3">
                          <Acciones articulo={a} onAccion={iniciarAccion} compacto />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Móvil y tablet */}
              <div className="space-y-3 lg:hidden">
                {articulos.map((a, i) => (
                  <article key={a.codigo} className="rounded-xl border-l-4 border-red-500 bg-white p-4 shadow-sm ring-1 ring-slate-200">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-400">
                          #{i + 1} · <span className="font-mono">{a.codigo}</span> · {a.grupo}
                        </p>
                        <p className="font-medium leading-snug text-slate-900">{a.descripcion}</p>
                      </div>
                      <DiasSinVender articulo={a} />
                    </div>
                    <dl className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3">
                      <div>
                        <dt className="text-[11px] text-slate-500">Existencia</dt>
                        <dd className="text-sm text-slate-700">
                          {a.existencia} × {usd(a.costo_unitario)}
                        </dd>
                        <dd>
                          <Ubicacion articulo={a} />
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[11px] text-slate-500">Capital estancado</dt>
                        <dd className="text-sm">
                          <ParticipacionCapital capital={a.capital_estancado} total={resumen.capital_total} />
                        </dd>
                      </div>
                    </dl>
                    <div className="mt-3">
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Seguimiento</p>
                      <Seguimiento articulo={a} onAbrirTraslado={onAbrirTraslado} onCerrarAccion={cerrarAccion} />
                    </div>
                    <div className="mt-3">
                      <Acciones articulo={a} onAccion={iniciarAccion} />
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {dialogo && (
        <Dialogo
          titulo={dialogo.titulo}
          textoConfirmar={dialogo.textoConfirmar}
          varianteConfirmar={dialogo.variante}
          campo={dialogo.campo}
          onCancelar={() => setDialogo(null)}
          onConfirmar={async (texto) => {
            await dialogo.accion(texto);
            setDialogo(null);
          }}
        >
          {dialogo.texto}
        </Dialogo>
      )}

      {retorno && (
        <DialogoRetorno
          articulo={retorno}
          onCancelar={() => setRetorno(null)}
          onConfirmar={async ({ origen, cantidad, comentario }) => {
            const t = await crearRetorno({ articulo_codigo: retorno.codigo, origen, cantidad, comentario });
            actualizarArticulo(retorno.codigo, (a) => ({
              ...a,
              retornos: [...a.retornos, { id: t.id, folio: t.folio, origen: t.origen, estado: t.estado, cantidad }],
            }));
            setRetorno(null);
            avisar({
              tono: 'exito',
              titulo: t.total_articulos > 1 ? `Agregado al borrador ${t.folio}` : `${t.folio} creado como borrador`,
              texto: 'Envía el documento a aprobación desde Traslados para iniciar el retorno.',
              accion: { texto: 'Abrir traslado', onClick: () => onAbrirTraslado(t.id) },
            });
          }}
        />
      )}
    </div>
  );
}
