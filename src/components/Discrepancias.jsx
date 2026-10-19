import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, ClipboardX, Inbox } from 'lucide-react';
import Encabezado, { EstadoVacio } from './ui/Encabezado.jsx';
import Aviso from './ui/Aviso.jsx';
import Boton from './ui/Boton.jsx';
import Dialogo from './ui/Dialogo.jsx';
import { useAvisos } from './ui/Avisos.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import { listarDiscrepancias, revisarDiscrepancia } from '../services/api.js';
import { fechaHora } from './traslados/estados.js';

const PESTANAS = [
  { id: 'pendiente', texto: 'Pendientes' },
  { id: 'revisada', texto: 'Revisadas' },
];

function Fila({ d, puedeRevisar, onRevisar }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
      <div className="min-w-0 flex-1 basis-64">
        <p className="font-medium text-slate-900">{d.articulo_nombre}</p>
        <p className="text-xs text-slate-500">
          <span className="font-mono">{d.articulo_codigo}</span> · {d.sucursal} · reportada por {d.creado_por} el {fechaHora(d.creado_en)}
        </p>
        {d.comentario && <p className="mt-1 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700">“{d.comentario}”</p>}
        {d.resolucion && (
          <p className="mt-1 text-xs text-emerald-800">
            Revisada por {d.revisado_por} el {fechaHora(d.revisado_en)}: {d.resolucion}
          </p>
        )}
      </div>
      <dl className="flex items-center gap-4 text-right">
        <div>
          <dt className="text-[11px] text-slate-500">Sistema</dt>
          <dd className="font-semibold tabular-nums text-slate-700">{d.existencia_sistema}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-slate-500">Contado</dt>
          <dd className="font-semibold tabular-nums text-slate-900">{d.existencia_contada}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-slate-500">Dif.</dt>
          <dd className="font-semibold tabular-nums text-red-700">
            {d.diferencia > 0 ? '+' : ''}
            {d.diferencia}
          </dd>
        </div>
        {puedeRevisar && d.estado === 'pendiente' && (
          <Boton tamano="sm" icono={CheckCircle2} onClick={() => onRevisar(d)}>
            Marcar revisada
          </Boton>
        )}
      </dl>
    </li>
  );
}

// El piso de venta ve las discrepancias de su tienda; compras y gerencia las de todas y las revisan.
export default function Discrepancias() {
  const { usuario, puede } = useAuth();
  const avisar = useAvisos();
  const [estado, setEstado] = useState('pendiente');
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [revision, setRevision] = useState(null);
  const puedeRevisar = puede('revisar_discrepancias');
  const sucursal = puedeRevisar ? undefined : usuario.sucursal;

  const cargar = useCallback(() => {
    listarDiscrepancias({ estado, sucursal })
      .then((r) => {
        setItems(r);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [estado, sucursal]);

  useEffect(() => {
    setItems(null);
    cargar();
  }, [cargar]);

  return (
    <div className="space-y-5">
      <Encabezado
        icono={ClipboardX}
        tono="bg-red-700"
        titulo="Discrepancias de inventario"
        subtitulo={
          puedeRevisar
            ? 'Diferencias entre lo contado en tienda y el sistema, reportadas por el piso de venta.'
            : `Lo que reportaste en ${usuario.sucursal}. Para reportar una nueva, búscala en «Precios y stock».`
        }
      />

      <div role="tablist" aria-label="Estado de las discrepancias" className="flex gap-1">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={estado === p.id}
            onClick={() => setEstado(p.id)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
              estado === p.id ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
            }`}
          >
            {p.texto}
          </button>
        ))}
      </div>

      {error && (
        <Aviso tono="error" titulo="No se pudieron cargar las discrepancias" accion={<Boton tamano="sm" onClick={cargar}>Reintentar</Boton>}>
          {error}
        </Aviso>
      )}
      {!items && !error && <div className="h-32 animate-pulse rounded-xl bg-slate-200/70" />}
      {items?.length === 0 && (
        <EstadoVacio icono={Inbox} titulo={estado === 'pendiente' ? 'No hay discrepancias pendientes' : 'Aún no hay discrepancias revisadas'} />
      )}
      {items?.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl bg-white ring-1 ring-slate-200">
          {items.map((d) => (
            <Fila key={d.id} d={d} puedeRevisar={puedeRevisar} onRevisar={setRevision} />
          ))}
        </ul>
      )}

      {revision && (
        <Dialogo
          titulo={`Revisar discrepancia · ${revision.articulo_nombre}`}
          textoConfirmar="Marcar revisada"
          campo={{ etiqueta: 'Qué se hizo', requerido: true, placeholder: 'Ej.: se recontó y se ajustó el inventario' }}
          onCancelar={() => setRevision(null)}
          onConfirmar={async (resolucion) => {
            await revisarDiscrepancia(revision.id, resolucion);
            setRevision(null);
            avisar({ tono: 'exito', titulo: 'Discrepancia revisada', texto: `${revision.articulo_nombre} · ${revision.sucursal}` });
            cargar();
          }}
        >
          {revision.sucursal}: el sistema registra {revision.existencia_sistema} u y se contaron {revision.existencia_contada} u.
        </Dialogo>
      )}
    </div>
  );
}
