import { useEffect, useState } from 'react';
import { ArrowRight, Check, Send, Trash2, Truck, PackageCheck, Archive, X, Save } from 'lucide-react';
import { AbcBadge, EstadoBadge } from '../Badges.jsx';
import Boton from '../ui/Boton.jsx';
import Aviso from '../ui/Aviso.jsx';
import Dialogo from '../ui/Dialogo.jsx';
import { obtenerTraslado } from '../../services/api.js';
import { CAMPOS, EVENTOS, SIGUIENTE_PASO, fechaHora } from './estados.js';

const ROL = { gerente: 'Gerente', analista: 'Analista' };

function Seccion({ titulo, children }) {
  return (
    <section className="border-b border-slate-100 px-5 py-4 last:border-0">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</h3>
      {children}
    </section>
  );
}

function Dato({ etiqueta, valor, destacado }) {
  return (
    <div className={`rounded-lg p-2.5 ${destacado ? 'bg-red-50 ring-1 ring-red-200' : 'bg-slate-50'}`}>
      <dt className="text-[11px] text-slate-500">{etiqueta}</dt>
      <dd className={`text-base font-semibold tabular-nums ${destacado ? 'text-red-800' : 'text-slate-900'}`}>{valor ?? '—'}</dd>
    </div>
  );
}

function CampoNumero({ id, etiqueta, valor, onChange, error, ayuda }) {
  return (
    <label htmlFor={id} className="block text-sm">
      <span className="font-medium text-slate-700">{etiqueta}</span>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={0}
        step={1}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-slate-900 sm:w-40 ${
          error ? 'border-red-400' : 'border-slate-300'
        }`}
      />
      {error ? (
        <span id={`${id}-error`} className="mt-1 block text-xs text-red-700">
          {error}
        </span>
      ) : (
        ayuda && <span className="mt-1 block text-xs text-slate-500">{ayuda}</span>
      )}
    </label>
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

const esEntero = (v, minimo) => v !== '' && Number.isInteger(Number(v)) && Number(v) >= minimo;

// Formulario de la siguiente acción según el estado y lo que el backend permite a este rol.
function AccionDisponible({ t, ejecutar, editar, procesando, pedirConfirmacion }) {
  const [cantidad, setCantidad] = useState('');
  const [comentario, setComentario] = useState('');
  const [errores, setErrores] = useState({});

  // Valores iniciales de cada etapa; se reinician cuando el traslado cambia de estado.
  useEffect(() => {
    const inicial = { borrador: t.cantidad_sugerida, pendiente_aprobacion: t.cantidad_sugerida, aprobado: t.cantidad_aprobada };
    setCantidad(inicial[t.estado] != null ? String(inicial[t.estado]) : '');
    setComentario('');
    setErrores({});
  }, [t.id, t.estado, t.cantidad_sugerida, t.cantidad_aprobada]);

  const a = t.acciones;
  const validar = (minimo, maximo, etiqueta) => {
    if (!esEntero(cantidad, minimo)) return `${etiqueta} debe ser un número entero mayor o igual a ${minimo}.`;
    if (maximo != null && Number(cantidad) > maximo) return `${etiqueta} no puede superar ${maximo}.`;
    return null;
  };
  const conErrores = (nuevos) => {
    setErrores(nuevos);
    return Object.values(nuevos).some(Boolean);
  };

  if (a.includes('enviar')) {
    const cambiada = cantidad !== String(t.cantidad_sugerida);
    return (
      <div className="space-y-3">
        <CampoNumero
          id="cantidad-borrador"
          etiqueta="Cantidad a trasladar"
          valor={cantidad}
          onChange={setCantidad}
          error={errores.cantidad}
          ayuda="Puedes ajustarla antes de enviarla a aprobación; el cambio queda en el historial."
        />
        <div className="flex flex-wrap gap-2">
          {cambiada ? (
            <Boton
              variante="primario"
              icono={Save}
              cargando={procesando}
              onClick={() => {
                if (!conErrores({ cantidad: validar(1, null, 'La cantidad') })) editar(t, { cantidad_sugerida: Number(cantidad) }).catch(() => {});
              }}
            >
              Guardar cantidad
            </Boton>
          ) : (
            <Boton variante="primario" icono={Send} cargando={procesando} onClick={() => ejecutar(t, 'enviar').catch(() => {})}>
              Enviar a aprobación
            </Boton>
          )}
          {a.includes('descartar') && (
            <Boton
              variante="peligro"
              icono={Trash2}
              disabled={procesando}
              onClick={() =>
                pedirConfirmacion({
                  titulo: `Descartar ${t.folio}`,
                  texto: 'La propuesta quedará descartada y no podrá enviarse a aprobación.',
                  textoConfirmar: 'Descartar',
                  variante: 'peligro',
                  campo: { etiqueta: 'Motivo', requerido: false, placeholder: 'Ej.: el producto se repondrá por compra directa' },
                  accion: (texto) => ejecutar(t, 'descartar', { comentario: texto }),
                })
              }
            >
              Descartar
            </Boton>
          )}
        </div>
      </div>
    );
  }

  if (a.includes('aprobar')) {
    return (
      <div className="space-y-3">
        <CampoNumero
          id="cantidad-aprobar"
          etiqueta="Cantidad a aprobar"
          valor={cantidad}
          onChange={setCantidad}
          error={errores.cantidad}
          ayuda={`Sugerida: ${t.cantidad_sugerida}. Se valida contra el stock disponible en ${t.origen}.`}
        />
        <CampoTexto id="comentario-aprobar" etiqueta="Comentario" opcional valor={comentario} onChange={setComentario} />
        <div className="flex flex-wrap gap-2">
          <Boton
            variante="exito"
            icono={Check}
            cargando={procesando}
            onClick={() => {
              if (!conErrores({ cantidad: validar(1, null, 'La cantidad') }))
                ejecutar(t, 'aprobar', { cantidad: Number(cantidad), comentario }).catch(() => {});
            }}
          >
            Aprobar
          </Boton>
          <Boton
            variante="peligro"
            icono={X}
            disabled={procesando}
            onClick={() =>
              pedirConfirmacion({
                titulo: `Rechazar ${t.folio}`,
                texto: `${t.articulo_nombre} · ${t.cantidad_sugerida} u hacia ${t.destino}.`,
                textoConfirmar: 'Rechazar',
                variante: 'peligro',
                campo: { etiqueta: 'Motivo del rechazo', requerido: true, placeholder: 'Ej.: hay una compra en camino' },
                accion: (texto) => ejecutar(t, 'rechazar', { motivo: texto }),
              })
            }
          >
            Rechazar
          </Boton>
        </div>
      </div>
    );
  }

  if (a.includes('despachar')) {
    return (
      <div className="space-y-3">
        <CampoNumero
          id="cantidad-despacho"
          etiqueta="Cantidad despachada"
          valor={cantidad}
          onChange={setCantidad}
          error={errores.cantidad}
          ayuda={`Aprobada: ${t.cantidad_aprobada}. Registra lo que realmente sale de ${t.origen}.`}
        />
        <CampoTexto id="comentario-despacho" etiqueta="Observaciones del despacho" opcional valor={comentario} onChange={setComentario} />
        <Boton
          variante="primario"
          icono={Truck}
          cargando={procesando}
          onClick={() => {
            if (!conErrores({ cantidad: validar(1, t.cantidad_aprobada, 'La cantidad despachada') }))
              ejecutar(t, 'despachar', { cantidad: Number(cantidad), comentario }).catch(() => {});
          }}
        >
          Registrar despacho
        </Boton>
      </div>
    );
  }

  if (a.includes('recibir')) {
    const diferencia = esEntero(cantidad, 0) ? Number(cantidad) - t.cantidad_despachada : 0;
    const registrar = () => ejecutar(t, 'recibir', { cantidad: Number(cantidad), comentario });
    return (
      <div className="space-y-3">
        <CampoNumero
          id="cantidad-recepcion"
          etiqueta="Cantidad recibida"
          valor={cantidad}
          onChange={setCantidad}
          error={errores.cantidad}
          ayuda={`Despachada: ${t.cantidad_despachada}. Cuenta la mercancía al recibirla.`}
        />
        {diferencia !== 0 && (
          <Aviso tono="advertencia">
            Diferencia de {diferencia > 0 ? '+' : ''}
            {diferencia} unidades respecto a lo despachado. Describe qué ocurrió.
          </Aviso>
        )}
        <CampoTexto
          id="comentario-recepcion"
          etiqueta="Observaciones de la recepción"
          opcional={diferencia === 0}
          valor={comentario}
          onChange={setComentario}
          error={errores.comentario}
          placeholder={diferencia ? 'Ej.: llegaron 2 unidades dañadas' : ''}
        />
        <Boton
          variante="primario"
          icono={PackageCheck}
          cargando={procesando}
          onClick={() => {
            const nuevos = {
              cantidad: validar(0, null, 'La cantidad recibida'),
              comentario: diferencia !== 0 && comentario.trim().length < 3 ? 'Describe la diferencia.' : null,
            };
            if (conErrores(nuevos)) return;
            if (diferencia !== 0) {
              pedirConfirmacion({
                titulo: 'Registrar recepción con diferencias',
                texto: `Se recibieron ${cantidad} de ${t.cantidad_despachada} unidades despachadas (${diferencia > 0 ? '+' : ''}${diferencia}). El traslado quedará marcado con diferencias para revisión.`,
                textoConfirmar: 'Registrar diferencia',
                variante: 'primario',
                accion: registrar,
              });
            } else {
              registrar().catch(() => {});
            }
          }}
        >
          Confirmar recepción
        </Boton>
      </div>
    );
  }

  if (a.includes('cerrar')) {
    const conDiferencias = t.estado === 'recibido_con_diferencias';
    return (
      <div className="space-y-3">
        <CampoTexto
          id="comentario-cierre"
          etiqueta={conDiferencias ? 'Conciliación de la diferencia' : 'Comentario de cierre'}
          opcional={!conDiferencias}
          valor={comentario}
          onChange={setComentario}
          error={errores.comentario}
          placeholder={conDiferencias ? 'Ej.: se registró merma de 2 unidades' : ''}
        />
        <Boton
          variante="primario"
          icono={Archive}
          cargando={procesando}
          onClick={() => {
            if (!conErrores({ comentario: conDiferencias && comentario.trim().length < 3 ? 'Indica cómo se concilió.' : null }))
              ejecutar(t, 'cerrar', { comentario }).catch(() => {});
          }}
        >
          Cerrar traslado
        </Boton>
      </div>
    );
  }

  // Sin acciones para este rol en el estado actual.
  const esperaGerente = ['pendiente_aprobacion', 'recibido', 'recibido_con_diferencias'].includes(t.estado);
  return (
    <p className="text-sm text-slate-600">
      {esperaGerente ? `${SIGUIENTE_PASO[t.estado]} Tu rol no tiene esta acción disponible.` : SIGUIENTE_PASO[t.estado]}
    </p>
  );
}

function Observaciones({ t, editar, procesando }) {
  const [texto, setTexto] = useState(t.observaciones ?? '');
  useEffect(() => setTexto(t.observaciones ?? ''), [t.id, t.observaciones]);
  const cambiado = texto.trim() !== (t.observaciones ?? '');
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
        <Boton tamano="sm" icono={Save} cargando={procesando} onClick={() => editar(t, { observaciones: texto }).catch(() => {})}>
          Guardar observaciones
        </Boton>
      )}
    </div>
  );
}

const valorCampo = (v) => (v === null || v === undefined || v === '' ? '—' : String(v));

function Historial({ eventos }) {
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {[...eventos].reverse().map((e) => {
        const { antes = {}, despues = {}, comentario } = e.detalle;
        const campos = [...new Set([...Object.keys(antes), ...Object.keys(despues)])];
        const incidencia = e.tipo === 'rechazado' || e.tipo === 'recibido_con_diferencias';
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
            {campos.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
                {campos.map((c) => (
                  <li key={c}>
                    {CAMPOS[c] ?? c}:{' '}
                    {c in antes && c in despues ? (
                      <>
                        <span className="text-slate-400 line-through">{valorCampo(antes[c])}</span> → <strong>{valorCampo(despues[c])}</strong>
                      </>
                    ) : (
                      <strong>{valorCampo(c in despues ? despues[c] : antes[c])}</strong>
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

export default function DetalleTraslado({ id, version, ejecutar, editar, procesando }) {
  const [t, setT] = useState(null);
  const [error, setError] = useState(null);
  const [confirmacion, setConfirmacion] = useState(null);

  // Se recarga al abrir y cuando la fila cambia en la lista (otra acción o sincronización con el servidor).
  useEffect(() => {
    let vigente = true;
    setError(null);
    obtenerTraslado(id)
      .then((d) => vigente && setT(d))
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
    };
  }, [id, version]);

  if (error) return <Aviso tono="error" className="m-5">{error}</Aviso>;
  if (!t) return <div className="m-5 h-64 animate-pulse rounded-xl bg-slate-100" />;

  // Las acciones devuelven el traslado actualizado (con historial); si el servidor lo rechaza por conflicto,
  // se muestra su versión real.
  const conSincronizacion = (fn) => async (...args) => {
    try {
      const nuevo = await fn(...args);
      setT(nuevo);
      return nuevo;
    } catch (e) {
      if (e.cuerpo?.traslado) setT(e.cuerpo.traslado);
      throw e;
    }
  };
  const ejecutarAqui = conSincronizacion(ejecutar);
  const editarAqui = conSincronizacion(editar);

  return (
    <div>
      <Seccion titulo="Resumen">
        <div className="flex flex-wrap items-center gap-2">
          <EstadoBadge estado={t.estado} />
          {t.tipo === 'retorno' && <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">Retorno al almacén</span>}
        </div>
        <p className="mt-2 text-sm text-slate-600">{SIGUIENTE_PASO[t.estado]}</p>
        <div className="mt-3 flex items-start gap-3">
          <AbcBadge clase={t.clasificacion_abc} />
          <div className="min-w-0">
            <p className="font-medium text-slate-900">{t.articulo_nombre}</p>
            <p className="font-mono text-xs text-slate-500">{t.articulo_codigo}</p>
          </div>
        </div>
        <p className="mt-3 inline-flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {t.origen} <ArrowRight className="h-4 w-4 text-slate-400" aria-label="hacia" /> {t.destino}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Creado el {fechaHora(t.creado_en)} por {t.creado_por ?? '—'}
          {t.horizonte_dias && ` · horizonte de ${t.horizonte_dias} días`}
        </p>
      </Seccion>

      <Seccion titulo="Cantidades">
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Dato etiqueta="Sugerida" valor={t.cantidad_sugerida} />
          <Dato etiqueta="Aprobada" valor={t.cantidad_aprobada} />
          <Dato etiqueta="Despachada" valor={t.cantidad_despachada} />
          <Dato etiqueta="Recibida" valor={t.cantidad_recibida} destacado={!!t.diferencia} />
        </dl>
        {!!t.diferencia && (
          <p className="mt-2 text-sm font-medium text-red-700">
            Diferencia en recepción: {t.diferencia > 0 ? '+' : ''}
            {t.diferencia} unidades
          </p>
        )}
        <dl className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-500">
          <div>
            <dt>Stock en origen al generar</dt>
            <dd className="font-medium text-slate-700">{t.stock_origen ?? '—'}</dd>
          </div>
          <div>
            <dt>Stock en destino al generar</dt>
            <dd className="font-medium text-slate-700">{t.stock_destino ?? '—'}</dd>
          </div>
          <div>
            <dt>Cobertura del destino</dt>
            <dd className="font-medium text-slate-700">{t.cobertura_dias != null ? `${t.cobertura_dias} días` : '—'}</dd>
          </div>
        </dl>
      </Seccion>

      {t.motivo_rechazo && (
        <Seccion titulo={t.estado === 'descartado' ? 'Motivo del descarte' : 'Motivo del rechazo'}>
          <Aviso tono="error">{t.motivo_rechazo}</Aviso>
        </Seccion>
      )}

      <Seccion titulo="Siguiente acción">
        <AccionDisponible t={t} ejecutar={ejecutarAqui} editar={editarAqui} procesando={procesando} pedirConfirmacion={setConfirmacion} />
      </Seccion>

      <Seccion titulo="Observaciones">
        <Observaciones t={t} editar={editarAqui} procesando={procesando} />
      </Seccion>

      <Seccion titulo={`Historial (${t.eventos.length})`}>
        <Historial eventos={t.eventos} />
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
