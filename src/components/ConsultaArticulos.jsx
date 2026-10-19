import { useEffect, useRef, useState } from 'react';
import { ClipboardX, DollarSign, Landmark, PackageSearch, Search, Tag, Wallet } from 'lucide-react';
import Encabezado, { EstadoVacio } from './ui/Encabezado.jsx';
import Aviso from './ui/Aviso.jsx';
import Boton from './ui/Boton.jsx';
import Dialogo from './ui/Dialogo.jsx';
import { AbcBadge } from './Badges.jsx';
import { useAvisos } from './ui/Avisos.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import { consultarStock, obtenerTasas, reportarDiscrepancia } from '../services/api.js';
import { fechaLocal } from '../utils/formato.js';

const IVA = 1.16;

const monto = (n) => n.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fechaCorta = (iso) => fechaLocal(iso).toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit' });

// Cada precio con su color fijo: verde tasa interna, morado bolívares, azul tasa BCV.
const MONEDAS = {
  interna: { titulo: 'Precio a tasa interna', icono: DollarSign, clase: 'bg-emerald-50 text-emerald-900 ring-emerald-200', acento: 'text-emerald-700' },
  bs: { titulo: 'Precio en bolívares', icono: Wallet, clase: 'bg-violet-50 text-violet-900 ring-violet-200', acento: 'text-violet-700' },
  bcv: { titulo: 'Precio a tasa BCV', icono: Landmark, clase: 'bg-sky-50 text-sky-900 ring-sky-200', acento: 'text-sky-700' },
};

function Precio({ moneda, valor, prefijo, detalle }) {
  const { titulo, icono: Icono, clase, acento } = MONEDAS[moneda];
  return (
    <div className={`rounded-xl p-4 ring-1 ${clase}`}>
      <p className={`flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide ${acento}`}>
        <Icono className="h-4 w-4" /> {titulo}
      </p>
      <p className="mt-1 text-3xl font-bold tabular-nums tracking-tight sm:text-4xl">
        {valor == null ? '—' : (
          <>
            <span className="mr-1 text-lg font-semibold opacity-70">{prefijo}</span>
            {monto(valor)}
          </>
        )}
      </p>
      {detalle && <p className="mt-1 text-xs opacity-75">{detalle}</p>}
    </div>
  );
}

// El precio sale de la ubicación del usuario; si allí no hay precio cargado, del almacén u otra ubicación.
function precioPara(articulo, ubicacion) {
  const conPrecio = articulo.existencias.filter((e) => e.precio_usd);
  return conPrecio.find((e) => e.ubicacion === ubicacion) ?? conPrecio[0] ?? null;
}

// PRECIO1EX + IVA es el precio en dólares a tasa interna; en bolívares se cobra a esa tasa, y el precio a tasa
// BCV es el equivalente en dólares de esos bolívares al cambio oficial.
function Precios({ articulo, ubicacion, tasas }) {
  const origen = precioPara(articulo, ubicacion);
  if (!origen) {
    return (
      <Aviso tono="advertencia" className="mt-3">
        Sin precio de venta en el inventario cargado. Pide que se vuelva a cargar el inventario de la tienda.
      </Aviso>
    );
  }
  const usd = origen.precio_usd * IVA;
  const bcv = tasas?.bcv?.valor;
  const interna = tasas?.interna?.valor;
  const bs = interna ? usd * interna : null;
  return (
    <>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Precio moneda="interna" prefijo="$" valor={usd} detalle={`Sin IVA: $${monto(origen.precio_usd)}`} />
        <Precio
          moneda="bs"
          prefijo="Bs"
          valor={bs}
          detalle={interna ? `Tasa interna ${monto(interna)} · ${fechaCorta(tasas.interna.fecha)}` : 'Sin tasa interna cargada'}
        />
        <Precio
          moneda="bcv"
          prefijo="$"
          valor={bs != null && bcv ? bs / bcv : null}
          detalle={bcv ? `Tasa BCV ${monto(bcv)} · ${fechaCorta(tasas.bcv.fecha)}` : 'Sin tasa BCV cargada'}
        />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Precio con IVA (16 %) de {origen.ubicacion === ubicacion ? 'tu ubicación' : origen.ubicacion}.
      </p>
    </>
  );
}

function Existencias({ articulo, ubicacion, puedeReportar, onReportar }) {
  if (articulo.existencias.length === 0) {
    return <p className="mt-3 text-sm text-slate-500">Sin existencias registradas en el inventario cargado.</p>;
  }
  return (
    <div className="mt-4">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Existencias</p>
      <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
        {articulo.existencias.map((e) => {
          const propia = e.ubicacion === ubicacion;
          return (
            <li key={e.ubicacion} className={`flex flex-wrap items-center justify-between gap-2 px-3 py-2 ${propia ? 'bg-sky-50/70' : ''}`}>
              <span className="text-sm text-slate-700">
                {e.ubicacion}
                {propia && <span className="ml-2 rounded bg-sky-100 px-1.5 text-[10px] font-semibold uppercase text-sky-800">tu ubicación</span>}
              </span>
              <span className="flex items-center gap-2">
                <span className="text-base font-semibold tabular-nums text-slate-900">{e.existencia}</span>
                {propia && puedeReportar && (e.discrepancia_pendiente ? (
                  <span className="text-xs font-medium text-amber-700">Discrepancia en revisión</span>
                ) : (
                  <Boton tamano="sm" variante="peligro" icono={ClipboardX} onClick={() => onReportar(articulo, e.existencia)}>
                    No coincide
                  </Boton>
                ))}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Lo contado físicamente no coincide con el sistema: se reporta con la cantidad real y una explicación.
function DialogoDiscrepancia({ articulo, ubicacion, existencia, onCancelar, onReportada }) {
  const [contada, setContada] = useState('');
  return (
    <Dialogo
      titulo="Reportar discrepancia"
      textoConfirmar="Reportar"
      campo={{ etiqueta: '¿Qué observaste?', requerido: true, placeholder: 'Ej.: en el anaquel solo hay 3 unidades' }}
      onCancelar={onCancelar}
      onConfirmar={async (comentario) => {
        if (contada === '' || !Number.isInteger(Number(contada)) || Number(contada) < 0) {
          throw new Error('Indica la cantidad contada (número entero, 0 o más).');
        }
        const d = await reportarDiscrepancia({ articulo_codigo: articulo.codigo, sucursal: ubicacion, existencia_contada: Number(contada), comentario });
        onReportada(d);
      }}
    >
      <p>
        <strong className="text-slate-900">{articulo.nombre}</strong> en {ubicacion}. El sistema registra{' '}
        <strong className="tabular-nums text-slate-900">{existencia}</strong> unidades.
      </p>
      <label className="mt-4 block text-sm">
        <span className="font-medium text-slate-700">Cantidad contada físicamente</span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          step={1}
          value={contada}
          onChange={(e) => setContada(e.target.value)}
          className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-slate-900"
        />
      </label>
    </Dialogo>
  );
}

// Consulta de un artículo desde la tienda o el almacén: precios multimoneda y existencias por ubicación.
// Cada parte se muestra solo si el rol tiene el permiso correspondiente.
export default function ConsultaArticulos() {
  const { usuario, puede } = useAuth();
  const avisar = useAvisos();
  const verPrecios = puede('consultar_precios');
  const verStock = puede('consultar_stock');
  const [termino, setTermino] = useState('');
  const [items, setItems] = useState(null);
  const [tasas, setTasas] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [reporte, setReporte] = useState(null);
  const ultima = useRef(0);
  const ubicacion = usuario.sucursal;

  useEffect(() => {
    if (!verPrecios) return;
    obtenerTasas(undefined, 1)
      .then(setTasas)
      .catch(() => setTasas({ bcv: null, interna: null }));
  }, [verPrecios]);

  const buscar = async (q) => {
    const solicitud = ++ultima.current;
    setCargando(true);
    try {
      const r = await consultarStock(q);
      if (solicitud === ultima.current) {
        setItems(r);
        setError(null);
      }
    } catch (e) {
      if (solicitud === ultima.current) setError(e.message);
    } finally {
      if (solicitud === ultima.current) setCargando(false);
    }
  };

  // Busca al dejar de escribir; solo vale la respuesta de la última búsqueda.
  useEffect(() => {
    const q = termino.trim();
    if (q.length < 2) {
      setItems(null);
      return undefined;
    }
    const t = setTimeout(() => buscar(q), 300);
    return () => clearTimeout(t);
  }, [termino]);

  return (
    <div className="space-y-5">
      <Encabezado
        icono={Tag}
        titulo={verPrecios && verStock ? 'Precios y stock' : verPrecios ? 'Precios' : 'Consultar stock'}
        subtitulo={`${verPrecios ? 'Precio de venta a tasa interna, en bolívares y a tasa BCV' : 'Existencias por ubicación'}${
          verPrecios && verStock ? ', y existencias por ubicación' : ''
        }${ubicacion ? ` · ${ubicacion}` : ''}.`}
      />

      <label className="relative block">
        <span className="sr-only">Buscar por código o nombre del producto</span>
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          autoFocus
          enterKeyHint="search"
          value={termino}
          onChange={(e) => setTermino(e.target.value)}
          placeholder="Código o nombre del producto"
          className="w-full rounded-2xl border border-slate-300 bg-white py-4 pl-12 pr-4 text-base focus:outline-none focus:ring-2 focus:ring-slate-900"
        />
      </label>

      {verPrecios && tasas && (!tasas.bcv || !tasas.interna) && (
        <Aviso tono="advertencia">Falta la tasa {!tasas.interna ? 'interna' : 'BCV'} del día: algunos precios no se pueden calcular.</Aviso>
      )}
      {error && <Aviso tono="error">{error}</Aviso>}

      {items === null && !error && (
        <EstadoVacio icono={Search} titulo="Busca un producto">
          Escribe al menos 2 caracteres del código o del nombre.
        </EstadoVacio>
      )}
      {items?.length === 0 && <EstadoVacio icono={PackageSearch} titulo="Ningún producto coincide con la búsqueda" />}
      {items?.length > 0 && (
        <div className={`space-y-3 ${cargando ? 'opacity-60' : ''}`}>
          {items.map((a) => (
            <article key={a.codigo} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:p-5">
              <div className="flex items-start gap-3">
                <AbcBadge clase={a.clasificacion_abc} />
                <div className="min-w-0">
                  <p className="text-lg font-semibold leading-snug text-slate-900">{a.nombre}</p>
                  <p className="text-xs text-slate-500">
                    <span className="font-mono">{a.codigo}</span>
                    {a.grupo && ` · ${a.grupo}`}
                  </p>
                </div>
              </div>
              {verPrecios && <Precios articulo={a} ubicacion={ubicacion} tasas={tasas} />}
              {verStock && (
                <Existencias
                  articulo={a}
                  ubicacion={ubicacion}
                  puedeReportar={puede('reportar_discrepancias')}
                  onReportar={(articulo, existencia) => setReporte({ articulo, existencia })}
                />
              )}
            </article>
          ))}
        </div>
      )}

      {reporte && (
        <DialogoDiscrepancia
          articulo={reporte.articulo}
          ubicacion={ubicacion}
          existencia={reporte.existencia}
          onCancelar={() => setReporte(null)}
          onReportada={(d) => {
            setReporte(null);
            avisar({ tono: 'exito', titulo: 'Discrepancia reportada', texto: `${d.articulo_nombre}: diferencia de ${d.diferencia > 0 ? '+' : ''}${d.diferencia} u. Queda en revisión.` });
            buscar(termino.trim());
          }}
        />
      )}
    </div>
  );
}
