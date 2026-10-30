import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Check, Send, Trash2, Truck, PackageCheck, Archive, X, Save, RotateCcw, Package, FileDown } from 'lucide-react';
import { AbcBadge, EstadoBadge } from '../Badges.jsx';
import Boton from '../ui/Boton.jsx';
import Aviso from '../ui/Aviso.jsx';
import Dialogo from '../ui/Dialogo.jsx';
import { exportarTraslado, obtenerTraslado } from '../../services/api.js';
import { useAvisos } from '../ui/Avisos.jsx';
import { ROLES } from '../../auth/roles.js';
import { CAMPOS, EVENTOS, SIGUIENTE_PASO, fechaHora } from './estados.js';

// Etiqueta del rol de quien hizo cada cambio; incluye el rol «analista» de registros anteriores.
const ROL = { analista: 'Analista', ...Object.fromEntries(Object.entries(ROLES).map(([id, r]) => [id, r.etiqueta])) };

// Cantidad que se captura por artículo en cada etapa: de qué valor parte, contra qué se compara y sus límites.
const CAPTURAS = {
  borrador: { accion: 'enviar', etiqueta: 'A trasladar', minimo: 1, inicial: (l) => l.cantidad_sugerida },
  pendiente_aprobacion: {
    accion: 'aprobar', etiqueta: 'A aprobar', minimo: 1, inicial: (l) => l.cantidad_sugerida,
    referencia: { etiqueta: 'Sugerida', valor: (l) => l.cantidad_sugerida },
  },
  aprobado: {
    accion: 'despachar', etiqueta: 'Despachada', minimo: 0, inicial: (l) => l.cantidad_aprobada, maximo: (l) => l.cantidad_aprobada,
    referencia: { etiqueta: 'Aprobada', valor: (l) => l.cantidad_aprobada },
  },
  despachado: {
    accion: 'recibir', etiqueta: 'Recibida', minimo: 0, inicial: (l) => l.cantidad_despachada,
    referencia: { etiqueta: 'Despachada', valor: (l) => l.cantidad_despachada },
  },
};

const ETAPAS = [
  ['cantidad_sugerida', 'Sugerida'],
  ['cantidad_aprobada', 'Aprobada'],
  ['cantidad_despachada', 'Despachada'],
  ['cantidad_recibida', 'Recibida'],
];

// Desde la aprobación el documento ya tiene cantidades definitivas para exportar.
const EXPORTABLES = ['aprobado', 'despachado', 'recibido', 'recibido_con_diferencias', 'cerrado'];

const esEntero = (v, minimo) => v !== '' && Number.isInteger(Number(v)) && Number(v) >= minimo;
const conSigno = (n) => `${n > 0 ? '+' : ''}${n}`;

function Seccion({ titulo, children, accion }) {
  return (
    <section className="border-b border-slate-100 px-5 py-4 last:border-0">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</h3>
        {accion}
      </div>
      {children}
    </section>
  );
}

function Indicador({ etiqueta, valor, tono }) {
  return (
    <div className={`rounded-lg p-2.5 ${tono === 'alerta' ? 'bg-red-50 ring-1 ring-red-200' : 'bg-slate-50'}`}>
      <dt className="text-[11px] text-slate-500">{etiqueta}</dt>
      <dd className={`text-lg font-semibold tabular-nums ${tono === 'alerta' ? 'text-red-800' : 'text-slate-900'}`}>{valor}</dd>
    </div>
  );
}

function CampoTexto({ id, etiqueta, valor, onChange, error, opcional, placeholder }) {
  return (
    <label htmlFor={id} className="block text-sm">
      <span className="font-medium text-slate-700">
        {etiqueta}
        {opcional && <span className="font-normal text-slate-400"> (opcional)</span>}
      </span>
      <textarea
        id={id}
        rows={2}
        value={valor}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 ${
          error ? 'border-red-400' : 'border-slate-300'
        }`}
      />
      {error && <span className="mt-1 block text-xs text-red-700">{error}</span>}
    </label>
  );
}

// Un artículo del documento: datos de contexto, cantidades por etapa y, si corresponde, el campo de la etapa actual.
function LineaArticulo({ l, captura, valor, error, onCambiar, puedeRetirar, unica, onRetirar, procesando }) {
  const diferenciaEnVivo =
    captura?.accion === 'recibir' && esEntero(valor, 0) ? Number(valor) - l.cantidad_despachada : null;
  const diferencia = diferenciaEnVivo ?? l.diferencia;
  const etapas = ETAPAS.filter(([campo]) => l[campo] != null);
  const modificada = captura && valor !== String(captura.inicial(l));

  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-3 ${modificada ? 'bg-amber-50/60' : ''}`}>
      <div className="flex min-w-0 flex-1 basis-56 items-start gap-3">
        <AbcBadge clase={l.clasificacion_abc} />
        <div className="min-w-0">
          <p className="font-medium leading-snug text-slate-900">{l.articulo_nombre}</p>
          <p className="text-xs text-slate-500">
            <span className="font-mono">{l.articulo_codigo}</span> · stock orig. {l.stock_origen ?? '—'} / dest.{' '}
            <span className={l.stock_destino != null && l.stock_destino < 3 ? 'font-semibold text-red-700' : ''}>{l.stock_destino ?? '—'}</span>
            {l.cobertura_dias != null && ` · cobertura ${l.cobertura_dias} d`}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {captura ? (
          captura.referencia && (
            <div className="text-right">
              <p className="text-[11px] text-slate-500">{captura.referencia.etiqueta}</p>
              <p className="text-sm font-medium tabular-nums text-slate-700">{captura.referencia.valor(l)}</p>
            </div>
          )
        ) : (
          etapas.map(([campo, etiqueta]) => (
            <div key={campo} className="text-right">
              <p className="text-[11px] text-slate-500">{etiqueta}</p>
              <p className="text-sm font-medium tabular-nums text-slate-700">{l[campo]}</p>
            </div>
          ))
        )}

        {captura && (
          <label className="block text-right">
            <span className="block text-[11px] font-medium text-slate-600">{captura.etiqueta}</span>
            <input
              type="number"
              inputMode="numeric"
              min={captura.minimo}
              max={captura.maximo?.(l)}
              step={1}
              value={valor}
              onChange={(e) => onCambiar(e.target.value)}
              aria-label={`${captura.etiqueta}: ${l.articulo_nombre}`}
              aria-invalid={!!error}
              className={`w-20 rounded-lg border px-2 py-1.5 text-right text-sm font-semibold tabular-nums focus:outline-none focus:ring-2 focus:ring-slate-900 ${
                error ? 'border-red-400 bg-red-50' : 'border-slate-300'
              }`}
            />
          </label>
        )}

        {diferencia != null && diferencia !== 0 && (
          <div className="text-right">
            <p className="text-[11px] text-slate-500">Dif.</p>
            <p className="text-sm font-semibold tabular-nums text-red-700">{conSigno(diferencia)}</p>
          </div>
        )}

        {puedeRetirar && (
          <Boton
            tamano="sm"
            variante="fantasma"
            disabled={unica || procesando}
            title={unica ? 'Es el único artículo: descarta el traslado completo' : undefined}
            aria-label={`Quitar ${l.articulo_nombre} del traslado`}
            onClick={onRetirar}
            className="hover:text-red-700"
          >
            <Trash2 className="h-4 w-4" />
          </Boton>
        )}
      </div>
      {error && <p className="basis-full text-right text-xs text-red-700">{error}</p>}
    </li>
  );
}

// Acciones sobre el documento completo según el estado y lo que el backend permite a este rol.
function AccionesDocumento({ d, captura, valores, setErrores, ejecutar, editar, procesando, pedirConfirmacion, onDeshacer }) {
  const [comentario, setComentario] = useState('');
  const [errorComentario, setErrorComentario] = useState(null);
  useEffect(() => {
    setComentario('');
    setErrorComentario(null);
  }, [d.id, d.estado]);

  const a = d.acciones;
  const lineas = d.lineas;
  const modificadas = captura ? lineas.filter((l) => valores[l.id] !== String(captura.inicial(l))) : [];

  // Valida todas las cantidades a la vez y marca cada artículo con error.
  const validar = () => {
    const nuevos = {};
    for (const l of lineas) {
      const v = valores[l.id];
      const maximo = captura.maximo?.(l);
      if (!esEntero(v, captura.minimo)) nuevos[l.id] = `Debe ser un entero mayor o igual a ${captura.minimo}.`;
      else if (maximo != null && Number(v) > maximo) nuevos[l.id] = `No puede superar ${maximo}.`;
    }
    setErrores(nuevos);
    return Object.keys(nuevos).length === 0;
  };
  const cantidades = () => Object.fromEntries(lineas.map((l) => [l.id, Number(valores[l.id])]));
  const unidades = captura ? lineas.reduce((s, l) => s + (Number(valores[l.id]) || 0), 0) : d.total_unidades;

  const descartar = () =>
    pedirConfirmacion({
      titulo: `Descartar ${d.folio}`,
      texto: `Se descartan los ${d.total_articulos} artículos del documento y no podrá enviarse a aprobación.`,
      textoConfirmar: 'Descartar traslado',
      variante: 'peligro',
      campo: { etiqueta: 'Motivo', requerido: false, placeholder: 'Ej.: se repondrá por compra directa' },
      accion: (texto) => ejecutar(d, 'descartar', { comentario: texto }),
    });

  const rechazar = () =>
    pedirConfirmacion({
      titulo: `Rechazar ${d.folio}`,
      texto: `${d.total_articulos} artículos · ${d.total_unidades} u de ${d.origen} a ${d.destino}.`,
      textoConfirmar: 'Rechazar traslado',
      variante: 'peligro',
      campo: { etiqueta: 'Motivo del rechazo', requerido: true, placeholder: 'Ej.: hay una compra en camino' },
      accion: (texto) => ejecutar(d, 'rechazar', { motivo: texto }),
    });

  const guardar = () => editar(d, { lineas: modificadas.map((l) => ({ id: l.id, cantidad_sugerida: Number(valores[l.id]) })) });

  let contenido;
  if (a.includes('enviar')) {
    const pendientes = modificadas.length;
    contenido = (
      <div className="flex flex-wrap gap-2">
        <Boton
          variante="primario"
          icono={Send}
          cargando={procesando}
          onClick={async () => {
            if (!validar()) return;
            try {
              const actual = pendientes ? await guardar() : d;
              await ejecutar(actual, 'enviar');
            } catch {
              /* el aviso ya informó el error */
            }
          }}
        >
          {pendientes ? 'Guardar y enviar a aprobación' : 'Enviar a aprobación'}
        </Boton>
        {pendientes > 0 && (
          <>
            <Boton icono={Save} disabled={procesando} onClick={() => validar() && guardar().catch(() => {})}>
              Guardar {pendientes} {pendientes === 1 ? 'cambio' : 'cambios'}
            </Boton>
            <Boton variante="fantasma" icono={RotateCcw} disabled={procesando} onClick={onDeshacer}>
              Deshacer
            </Boton>
          </>
        )}
        {a.includes('descartar') && (
          <Boton variante="peligro" icono={Trash2} disabled={procesando} onClick={descartar} className="sm:ml-auto">
            Descartar traslado
          </Boton>
        )}
      </div>
    );
  } else if (a.includes('aprobar')) {
    contenido = (
      <div className="space-y-3">
        <CampoTexto id="comentario-aprobar" etiqueta="Comentario" opcional valor={comentario} onChange={setComentario} />
        <div className="flex flex-wrap gap-2">
          <Boton
            variante="exito"
            icono={Check}
            cargando={procesando}
            onClick={() => validar() && ejecutar(d, 'aprobar', { cantidades: cantidades(), comentario }).catch(() => {})}
          >
            Aprobar traslado completo
          </Boton>
          {modificadas.length > 0 && (
            <Boton variante="fantasma" icono={RotateCcw} disabled={procesando} onClick={onDeshacer}>
              Volver a lo sugerido
            </Boton>
          )}
          {a.includes('rechazar') && (
            <Boton variante="peligro" icono={X} disabled={procesando} onClick={rechazar} className="sm:ml-auto">
              Rechazar traslado
            </Boton>
          )}
        </div>
      </div>
    );
  } else if (a.includes('despachar')) {
    contenido = (
      <div className="space-y-3">
        <CampoTexto id="comentario-despacho" etiqueta="Observaciones del despacho" opcional valor={comentario} onChange={setComentario} />
        <Boton
          variante="primario"
          icono={Truck}
          cargando={procesando}
          onClick={() => validar() && ejecutar(d, 'despachar', { cantidades: cantidades(), comentario }).catch(() => {})}
        >
          Registrar despacho
        </Boton>
      </div>
    );
  } else if (a.includes('recibir')) {
    const conDiferencia = modificadas;
    const registrar = () => ejecutar(d, 'recibir', { cantidades: cantidades(), comentario });
    contenido = (
      <div className="space-y-3">
        {conDiferencia.length > 0 && (
          <Aviso tono="advertencia">
            {conDiferencia.length} {conDiferencia.length === 1 ? 'artículo no coincide' : 'artículos no coinciden'} con lo despachado.
            Describe qué ocurrió.
          </Aviso>
        )}
        <CampoTexto
          id="comentario-recepcion"
          etiqueta="Observaciones de la recepción"
          opcional={conDiferencia.length === 0}
          valor={comentario}
          onChange={(v) => {
            setComentario(v);
            setErrorComentario(null);
          }}
          error={errorComentario}
          placeholder={conDiferencia.length ? 'Ej.: llegaron 2 unidades dañadas' : ''}
        />
        <Boton
          variante="primario"
          icono={PackageCheck}
          cargando={procesando}
          onClick={() => {
            if (!validar()) return;
            if (conDiferencia.length === 0) {
              registrar().catch(() => {});
              return;
            }
            if (comentario.trim().length < 3) {
              setErrorComentario('Describe la diferencia.');
              return;
            }
            pedirConfirmacion({
              titulo: 'Registrar recepción con diferencias',
              texto: (
                <>
                  <p>El traslado quedará marcado con diferencias para revisión del gerente:</p>
                  <ul className="mt-2 space-y-1 rounded-lg bg-slate-50 p-2 text-xs">
                    {conDiferencia.map((l) => (
                      <li key={l.id} className="flex justify-between gap-2">
                        <span className="truncate">{l.articulo_nombre}</span>
                        <span className="shrink-0 tabular-nums">
                          {valores[l.id]} de {l.cantidad_despachada} ({conSigno(Number(valores[l.id]) - l.cantidad_despachada)})
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              ),
              textoConfirmar: 'Registrar diferencia',
              variante: 'primario',
              accion: registrar,
            });
          }}
        >
          Confirmar recepción
        </Boton>
      </div>
    );
  } else if (a.includes('cerrar')) {
    const conDiferencias = d.estado === 'recibido_con_diferencias';
    contenido = (
      <div className="space-y-3">
        <CampoTexto
          id="comentario-cierre"
          etiqueta={conDiferencias ? 'Conciliación de la diferencia' : 'Comentario de cierre'}
          opcional={!conDiferencias}
          valor={comentario}
          onChange={(v) => {
            setComentario(v);
            setErrorComentario(null);
          }}
          error={errorComentario}
          placeholder={conDiferencias ? 'Ej.: se registró merma de 2 unidades' : ''}
        />
        <Boton
          variante="primario"
          icono={Archive}
          cargando={procesando}
          onClick={() => {
            if (conDiferencias && comentario.trim().length < 3) setErrorComentario('Indica cómo se concilió.');
            else ejecutar(d, 'cerrar', { comentario }).catch(() => {});
          }}
        >
          Cerrar traslado
        </Boton>
      </div>
    );
  } else {
    const esperaGerente = ['pendiente_aprobacion', 'recibido', 'recibido_con_diferencias'].includes(d.estado);
    return (
      <p className="border-t border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-600">
        {esperaGerente ? `${SIGUIENTE_PASO[d.estado]} Tu rol no tiene esta acción disponible.` : SIGUIENTE_PASO[d.estado]}
      </p>
    );
  }

  return (
    <div className="sticky bottom-0 z-10 space-y-2 border-t border-slate-200 bg-white px-5 py-4 shadow-[0_-4px_12px_-6px_rgba(15,23,42,0.15)]">
      <p className="text-xs text-slate-500">
        Aplica a los <strong className="text-slate-700">{lineas.length} artículos</strong> ·{' '}
        <strong className="tabular-nums text-slate-700">{unidades} unidades</strong>
      </p>
      {contenido}
    </div>
  );
}

function Observaciones({ d, editar, procesando }) {
  const [texto, setTexto] = useState(d.observaciones ?? '');
  useEffect(() => setTexto(d.observaciones ?? ''), [d.id, d.observaciones]);
  const cambiado = texto.trim() !== (d.observaciones ?? '');
  return (
    <div className="space-y-2">
      <textarea
        aria-label="Observaciones del traslado"
        rows={2}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        placeholder="Notas internas sobre esta operación"
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900"
      />
      {cambiado && (
        <Boton tamano="sm" icono={Save} cargando={procesando} onClick={() => editar(d, { observaciones: texto }).catch(() => {})}>
          Guardar observaciones
        </Boton>
      )}
    </div>
  );
}

const valorCampo = (v) => (v === null || v === undefined || v === '' ? '—' : String(v));

function Cambios({ antes = {}, despues = {} }) {
  const campos = [...new Set([...Object.keys(antes), ...Object.keys(despues)])];
  return campos.map((c, i) => (
    <span key={c}>
      {i > 0 && ' · '}
      {CAMPOS[c] ?? c}:{' '}
      {c in antes && c in despues ? (
        <>
          <span className="text-slate-400 line-through">{valorCampo(antes[c])}</span> → <strong>{valorCampo(despues[c])}</strong>
        </>
      ) : (
        <strong>{valorCampo(c in despues ? despues[c] : antes[c])}</strong>
      )}
    </span>
  ));
}

function Historial({ eventos }) {
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {[...eventos].reverse().map((e) => {
        const { antes, despues, comentario, articulos = [] } = e.detalle;
        const incidencia = ['rechazado', 'recibido_con_diferencias', 'articulo_retirado'].includes(e.tipo);
        return (
          <li key={e.id} className="relative">
            <span
              className={`absolute -left-[26px] top-1 h-3 w-3 rounded-full ring-4 ring-white ${incidencia ? 'bg-red-500' : 'bg-slate-400'}`}
              aria-hidden="true"
            />
            <p className="text-sm font-medium text-slate-900">{EVENTOS[e.tipo] ?? e.tipo}</p>
            <p className="text-xs text-slate-500">
              {fechaHora(e.fecha)} · {e.usuario}
              {e.rol && ` (${ROL[e.rol] ?? e.rol})`}
            </p>
            {(antes || despues) && (
              <p className="mt-1 text-xs text-slate-600">
                <Cambios antes={antes} despues={despues} />
              </p>
            )}
            {articulos.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
                {articulos.map((art) => (
                  <li key={art.codigo}>
                    <span className="font-medium text-slate-700">{art.nombre}</span>
                    {(art.antes || art.despues) && (
                      <>
                        {' — '}
                        <Cambios antes={art.antes} despues={art.despues} />
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {comentario && <p className="mt-1 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700">“{comentario}”</p>}
          </li>
        );
      })}
    </ol>
  );
}

const valoresIniciales = (d) => {
  const captura = d && CAPTURAS[d.estado];
  return captura ? Object.fromEntries(d.lineas.map((l) => [l.id, String(captura.inicial(l) ?? '')])) : {};
};

export default function DetalleTraslado({ id, version, ejecutar, editar, retirar, procesando }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);
  const [confirmacion, setConfirmacion] = useState(null);
  // Cantidades capturadas: parten de la etapa anterior y se descartan con cada nueva versión del documento.
  const [edicion, setEdicion] = useState({ clave: null, valores: {} });
  const [errores, setErrores] = useState({});
  const [exportando, setExportando] = useState(false);
  const avisar = useAvisos();

  // Se recarga al abrir y cuando la fila cambia en la lista (otra acción o sincronización con el servidor).
  useEffect(() => {
    let vigente = true;
    setError(null);
    obtenerTraslado(id)
      .then((nuevo) => vigente && setD(nuevo))
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
    };
  }, [id, version]);

  const clave = d && `${d.id}-${d.version}`;
  useEffect(() => setErrores({}), [clave]);

  const captura = useMemo(() => {
    const c = d && CAPTURAS[d.estado];
    return c && d.acciones.includes(c.accion) ? c : null;
  }, [d]);

  const valores = edicion.clave === clave ? edicion.valores : valoresIniciales(d);
  const cambiarValor = (lineaId, v) => setEdicion({ clave, valores: { ...valores, [lineaId]: v } });

  if (error) return <Aviso tono="error" className="m-5">{error}</Aviso>;
  if (!d) return <div className="m-5 h-64 animate-pulse rounded-xl bg-slate-100" />;

  // Las acciones devuelven el documento actualizado (con historial); si el servidor lo rechaza por conflicto,
  // se muestra su versión real.
  const conSincronizacion = (fn) => async (...args) => {
    try {
      const nuevo = await fn(...args);
      setD(nuevo);
      return nuevo;
    } catch (e) {
      if (e.cuerpo?.traslado) setD(e.cuerpo.traslado);
      throw e;
    }
  };
  const ejecutarAqui = conSincronizacion(ejecutar);
  const editarAqui = conSincronizacion(editar);
  const retirarAqui = conSincronizacion(retirar);

  const pedirRetiro = (l) =>
    setConfirmacion({
      titulo: `Quitar ${l.articulo_nombre}`,
      texto: `Se quita del ${d.folio}; el resto de los artículos sigue igual. El cambio queda en el historial.`,
      textoConfirmar: 'Quitar artículo',
      variante: 'peligro',
      campo: { etiqueta: 'Motivo', requerido: false, placeholder: 'Ej.: la sucursal tiene una compra en camino' },
      accion: (texto) => retirarAqui(d, l, texto),
    });

  return (
    <div>
      <Seccion
        titulo="Resumen"
        accion={
          EXPORTABLES.includes(d.estado) && (
            <Boton
              tamano="sm"
              icono={FileDown}
              cargando={exportando}
              onClick={() => {
                setExportando(true);
                exportarTraslado(d.id)
                  .catch((e) => avisar({ tono: 'error', titulo: `No se pudo exportar ${d.folio}`, texto: e.message }))
                  .finally(() => setExportando(false));
              }}
            >
              Exportar Excel
            </Boton>
          )
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <EstadoBadge estado={d.estado} />
          {d.tipo === 'retorno' && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">Retorno al almacén</span>}
        </div>
        <p className="mt-2 text-sm text-slate-600">{SIGUIENTE_PASO[d.estado]}</p>
        <p className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {d.origen} <ArrowRight className="h-4 w-4 text-slate-400" aria-label="hacia" /> <strong className="font-semibold">{d.destino}</strong>
        </p>
        <dl className="mt-3 grid grid-cols-3 gap-2">
          <Indicador etiqueta="Artículos" valor={d.total_articulos} />
          <Indicador etiqueta="Unidades" valor={d.total_unidades} />
          <Indicador etiqueta="Con diferencia" valor={d.con_diferencias} tono={d.con_diferencias ? 'alerta' : undefined} />
        </dl>
        <p className="mt-2 text-xs text-slate-500">
          Creado el {fechaHora(d.creado_en)} por {d.creado_por ?? '—'}
          {d.horizonte_dias && ` · horizonte de ${d.horizonte_dias} días`}
        </p>
      </Seccion>

      {d.motivo_rechazo && (
        <Seccion titulo={d.estado === 'descartado' ? 'Motivo del descarte' : 'Motivo del rechazo'}>
          <Aviso tono="error">{d.motivo_rechazo}</Aviso>
        </Seccion>
      )}

      <Seccion
        titulo={`Artículos (${d.lineas.length})`}
        accion={
          captura && (
            <span className="inline-flex items-center gap-1 text-xs text-slate-500">
              <Package className="h-3.5 w-3.5" /> Ajusta solo lo que cambie
            </span>
          )
        }
      >
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl ring-1 ring-slate-200">
          {d.lineas.map((l) => (
            <LineaArticulo
              key={l.id}
              l={l}
              captura={captura}
              valor={valores[l.id] ?? ''}
              error={errores[l.id]}
              onCambiar={(v) => {
                cambiarValor(l.id, v);
                setErrores(({ [l.id]: _, ...resto }) => resto);
              }}
              puedeRetirar={d.retirable}
              unica={d.lineas.length === 1}
              onRetirar={() => pedirRetiro(l)}
              procesando={procesando}
            />
          ))}
        </ul>
      </Seccion>

      <AccionesDocumento
        d={d}
        captura={captura}
        valores={valores}
        setErrores={setErrores}
        ejecutar={ejecutarAqui}
        editar={editarAqui}
        procesando={procesando}
        pedirConfirmacion={setConfirmacion}
        onDeshacer={() => {
          setEdicion({ clave: null, valores: {} });
          setErrores({});
        }}
      />

      <Seccion titulo="Observaciones">
        <Observaciones d={d} editar={editarAqui} procesando={procesando} />
      </Seccion>

      <Seccion titulo={`Historial (${d.eventos.length})`}>
        <Historial eventos={d.eventos} />
      </Seccion>

      {confirmacion && (
        <Dialogo
          titulo={confirmacion.titulo}
          textoConfirmar={confirmacion.textoConfirmar}
          varianteConfirmar={confirmacion.variante}
          campo={confirmacion.campo}
          onCancelar={() => setConfirmacion(null)}
          onConfirmar={async (texto) => {
            await confirmacion.accion(texto);
            setConfirmacion(null);
          }}
        >
          {confirmacion.texto}
        </Dialogo>
      )}
    </div>
  );
}
