import { useCallback, useEffect, useState } from 'react';
import { Megaphone, Inbox } from 'lucide-react';
import Encabezado, { EstadoVacio } from './ui/Encabezado.jsx';
import Aviso from './ui/Aviso.jsx';
import Boton from './ui/Boton.jsx';
import { listarAccionesEstancado } from '../services/api.js';
import { fechaHora } from './traslados/estados.js';

// Promociones registradas por compras o gerencia sobre mercancía estancada, que el piso de venta debe aplicar.
export default function Promociones() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  const cargar = useCallback(() => {
    listarAccionesEstancado('pendiente', 'promocion')
      .then((r) => {
        setItems(r);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <div className="space-y-5">
      <Encabezado
        icono={Megaphone}
        tono="bg-amber-600"
        titulo="Promociones entrantes"
        subtitulo="Solicitudes de promoción en curso para mover mercancía estancada."
      />

      {error && (
        <Aviso tono="error" titulo="No se pudieron cargar las promociones" accion={<Boton tamano="sm" onClick={cargar}>Reintentar</Boton>}>
          {error}
        </Aviso>
      )}
      {!items && !error && <div className="h-32 animate-pulse rounded-xl bg-slate-200/70" />}
      {items?.length === 0 && <EstadoVacio icono={Inbox} titulo="No hay promociones en curso" />}
      {items?.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {items.map((p) => (
            <li key={p.id} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
              <p className="font-medium leading-snug text-slate-900">{p.articulo_nombre}</p>
              <p className="font-mono text-xs text-slate-500">{p.articulo_codigo}</p>
              {p.comentario && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{p.comentario}</p>}
              <p className="mt-2 text-xs text-slate-500">
                Solicitada por {p.creado_por ?? '—'} el {fechaHora(p.creado_en)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
