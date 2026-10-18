import { useCallback, useEffect, useState } from 'react';
import { Database, Upload, FileText, ChevronDown, Store, CheckCircle2, XCircle, History } from 'lucide-react';
import FileDropzone from './FileDropzone.jsx';
import Encabezado from './ui/Encabezado.jsx';
import Boton from './ui/Boton.jsx';
import Aviso from './ui/Aviso.jsx';
import { cargarArchivoInicial, listarImportaciones } from '../services/api.js';
import { capitalizar, fechaLocal } from '../utils/formato.js';
import { fechaHora } from './traslados/estados.js';

const TIPOS_REPORTE = [
  { value: 'ventas', label: 'Historial de Ventas' },
  { value: 'inv_inval', label: 'Inventario Almacén Principal' },
  { value: 'inv_fisico', label: 'Inventario Sucursales' },
  { value: 'tasas', label: 'Tasas internas (hoja TASA del libro de pedidos)' },
];
const ETIQUETA_TIPO = { ventas: 'Ventas', inv_inval: 'Inventario almacén', inv_fisico: 'Inventario sucursal', tasas: 'Tasas internas' };

// "VENTAS BARCELONA.XLS" / "INVENTARIO MATURIN.XLS" -> "Barcelona" / "Maturin"
const sugerirSucursal = (nombreArchivo) =>
  capitalizar(
    nombreArchivo
      .replace(/\.[^.]+$/, '')
      .replace(/[_-]+/g, ' ')
      .replace(/\b(ventas?|inventarios?|inv)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim()
  );

function HistorialImportaciones({ importaciones, error }) {
  if (error) return <Aviso tono="error">No se pudo cargar el historial de importaciones: {error}</Aviso>;
  if (!importaciones) return <div className="h-24 animate-pulse rounded-xl bg-slate-200/70" />;
  if (importaciones.length === 0) return <p className="text-sm text-slate-500">Todavía no se ha registrado ninguna importación.</p>;
  return (
    <ul className="divide-y divide-slate-100 rounded-xl bg-white ring-1 ring-slate-200">
      {importaciones.map((i) => (
        <li key={i.id} className="flex items-start gap-3 px-4 py-3 text-sm">
          {i.exito ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="Importación correcta" />
          ) : (
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" aria-label="Importación con error" />
          )}
          <div className="min-w-0 flex-1">
            <p className="font-medium text-slate-900">
              {ETIQUETA_TIPO[i.tipo_reporte] ?? i.tipo_reporte}
              {i.sucursal && ` · ${i.sucursal}`}
              <span className="font-normal text-slate-500"> · {i.archivo}</span>
            </p>
            <p className="text-xs text-slate-500">
              Importado el {fechaHora(i.fecha_importacion)} por {i.usuario ?? '—'}
              {i.datos_hasta && ` · datos hasta el ${fechaLocal(i.datos_hasta).toLocaleDateString('es-VE')}`}
            </p>
            <p className={`mt-0.5 text-xs ${i.exito ? 'text-slate-500' : 'text-red-700'}`}>{i.mensaje}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function ConfiguracionInicial() {
  const [tipoReporte, setTipoReporte] = useState(TIPOS_REPORTE[0].value);
  const [archivo, setArchivo] = useState(null);
  const [sucursal, setSucursal] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [mensaje, setMensaje] = useState(null); // { tipo: 'exito' | 'error', texto }
  const [importaciones, setImportaciones] = useState(null);
  const [errorHistorial, setErrorHistorial] = useState(null);

  // Ventas e inventario de sucursal no indican la sucursal en el archivo.
  const pideSucursal = tipoReporte === 'ventas' || tipoReporte === 'inv_fisico';
  const faltaSucursal = pideSucursal && !sucursal.trim();

  const cargarHistorial = useCallback(() => {
    listarImportaciones()
      .then((l) => {
        setImportaciones(l);
        setErrorHistorial(null);
      })
      .catch((e) => setErrorHistorial(e.message));
  }, []);

  useEffect(() => {
    cargarHistorial();
  }, [cargarHistorial]);

  const procesar = async (e) => {
    e.preventDefault();
    if (!archivo || faltaSucursal) return;

    setIsLoading(true);
    setMensaje(null);
    try {
      const data = await cargarArchivoInicial(tipoReporte, archivo, pideSucursal ? sucursal.trim() : null);
      if (data.success) {
        setMensaje({ tipo: 'exito', texto: data.message || 'Archivo procesado correctamente.' });
        setArchivo(null);
      } else {
        // Ante un error se conservan el archivo, el tipo y la sucursal elegidos para reintentar.
        setMensaje({ tipo: 'error', texto: data.error || data.message || 'No se pudo procesar el archivo.' });
      }
    } catch {
      setMensaje({
        tipo: 'error',
        texto: 'No se pudo conectar con el servidor. Verifica que el backend esté activo en el puerto 5000.',
      });
    } finally {
      setIsLoading(false);
      cargarHistorial();
    }
  };

  return (
    <div className="space-y-6">
      <Encabezado icono={Database} titulo="Configuración inicial" subtitulo="Carga de datos base desde archivos del sistema administrativo" />

      <Aviso tono="advertencia" titulo="Módulo de carga manual activo (Fase de Mockup).">
        Esta vista será deshabilitada cuando se establezca la conexión ODBC a los servidores de producción.
      </Aviso>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <form onSubmit={procesar} className="space-y-6 rounded-2xl bg-white p-5 ring-1 ring-slate-200 sm:p-6">
          <fieldset disabled={isLoading} className="space-y-6">
            <div>
              <label htmlFor="tipo_reporte" className="mb-2 block text-sm font-medium text-slate-700">
                1. Tipo de reporte
              </label>
              <div className="relative">
                <FileText className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <select
                  id="tipo_reporte"
                  value={tipoReporte}
                  onChange={(e) => setTipoReporte(e.target.value)}
                  className="w-full appearance-none rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-10 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                >
                  {TIPOS_REPORTE.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium text-slate-700">2. Archivo</p>
              <FileDropzone
                archivo={archivo}
                deshabilitado={isLoading}
                onSeleccionar={(f) => {
                  setArchivo(f);
                  if (f) setSucursal(sugerirSucursal(f.name));
                  setMensaje(null);
                }}
                onError={(texto) => setMensaje({ tipo: 'error', texto })}
              />
            </div>

            {pideSucursal && (
              <div>
                <label htmlFor="sucursal" className="mb-2 block text-sm font-medium text-slate-700">
                  3. Sucursal
                </label>
                <div className="relative">
                  <Store className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="sucursal"
                    type="text"
                    value={sucursal}
                    onChange={(e) => setSucursal(e.target.value)}
                    placeholder="Ej. Barcelona"
                    aria-invalid={!!archivo && faltaSucursal}
                    aria-describedby="sucursal-ayuda"
                    className={`w-full rounded-xl border bg-white py-3 pl-10 pr-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900 ${
                      archivo && faltaSucursal ? 'border-red-400' : 'border-slate-300'
                    }`}
                  />
                </div>
                <p id="sucursal-ayuda" className={`mt-1.5 text-xs ${archivo && faltaSucursal ? 'text-red-700' : 'text-slate-500'}`}>
                  {archivo && faltaSucursal
                    ? 'Indica la sucursal para poder procesar el archivo.'
                    : `El reporte no indica la sucursal. Al cargarlo se reemplazan solo ${tipoReporte === 'ventas' ? 'las ventas' : 'el inventario'} de esta sucursal.`}
                </p>
              </div>
            )}
          </fieldset>

          {mensaje && (
            <Aviso
              tono={mensaje.tipo === 'exito' ? 'exito' : 'error'}
              accion={
                <button onClick={() => setMensaje(null)} type="button" className="text-xs font-medium opacity-70 hover:opacity-100">
                  Cerrar
                </button>
              }
            >
              {mensaje.texto}
            </Aviso>
          )}

          <Boton type="submit" variante="primario" icono={Upload} cargando={isLoading} disabled={!archivo || faltaSucursal} className="w-full sm:w-auto">
            {isLoading ? 'Cargando...' : 'Procesar Archivo'}
          </Boton>
        </form>

        <section className="space-y-3">
          <h2 className="inline-flex items-center gap-2 font-semibold text-slate-900">
            <History className="h-4 w-4 text-slate-400" /> Historial de importaciones
          </h2>
          <p className="text-xs text-slate-500">
            La fecha de importación es cuándo se cargó el archivo; «datos hasta» es la última fecha contenida en él (ventas y tasas).
          </p>
          <HistorialImportaciones importaciones={importaciones} error={errorHistorial} />
        </section>
      </div>
    </div>
  );
}
