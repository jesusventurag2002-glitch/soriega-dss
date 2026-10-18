import { useState } from 'react';
import { Database, AlertTriangle, CheckCircle2, XCircle, Loader2, Upload, FileText, ChevronDown, Store } from 'lucide-react';
import FileDropzone from './FileDropzone.jsx';
import { cargarArchivoInicial } from '../services/api.js';
import { capitalizar } from '../utils/formato.js';

const TIPOS_REPORTE = [
  { value: 'ventas', label: 'Historial de Ventas' },
  { value: 'inv_inval', label: 'Inventario Almacén Principal' },
  { value: 'inv_fisico', label: 'Inventario Sucursales' },
];

function Alerta({ tipo, texto, onCerrar }) {
  const exito = tipo === 'exito';
  const Icono = exito ? CheckCircle2 : XCircle;
  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-xl p-4 ring-1 ${
        exito ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : 'bg-red-50 text-red-800 ring-red-200'
      }`}
    >
      <Icono className="h-5 w-5 shrink-0 mt-0.5" />
      <p className="flex-1 text-sm">{texto}</p>
      <button onClick={onCerrar} className="text-xs font-medium opacity-70 hover:opacity-100">
        Cerrar
      </button>
    </div>
  );
}

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

export default function ConfiguracionInicial() {
  const [tipoReporte, setTipoReporte] = useState(TIPOS_REPORTE[0].value);
  const [archivo, setArchivo] = useState(null);
  const [sucursal, setSucursal] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [mensaje, setMensaje] = useState(null); // { tipo: 'exito' | 'error', texto }

  // Ventas e inventario de sucursal no indican la sucursal en el archivo.
  const pideSucursal = tipoReporte === 'ventas' || tipoReporte === 'inv_fisico';
  const faltaSucursal = pideSucursal && !sucursal.trim();

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
        setMensaje({ tipo: 'error', texto: data.error || data.message || 'No se pudo procesar el archivo.' });
      }
    } catch {
      setMensaje({
        tipo: 'error',
        texto: 'No se pudo conectar con el servidor. Verifica que el backend esté activo en el puerto 5000.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-slate-900 text-white flex items-center justify-center">
          <Database className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Configuración inicial</h1>
          <p className="text-sm text-slate-500">Carga de datos base desde archivos del sistema administrativo</p>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-xl border-l-4 border-amber-500 bg-amber-50 p-4 ring-1 ring-amber-200">
        <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
        <div className="text-sm text-amber-900">
          <p className="font-semibold">Módulo de carga manual activo (Fase de Mockup).</p>
          <p>Esta vista será deshabilitada cuando se establezca la conexión ODBC a los servidores de producción.</p>
        </div>
      </div>

      <form onSubmit={procesar} className="max-w-2xl rounded-2xl bg-white p-5 sm:p-6 ring-1 ring-slate-200 space-y-6">
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
                  className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-10 pr-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                />
              </div>
              <p className="mt-1.5 text-xs text-slate-500">
                El reporte no indica la sucursal. Al cargarlo se reemplazan solo{' '}
                {tipoReporte === 'ventas' ? 'las ventas' : 'el inventario'} de esta sucursal.
              </p>
            </div>
          )}
        </fieldset>

        {mensaje && <Alerta {...mensaje} onCerrar={() => setMensaje(null)} />}

        <button
          type="submit"
          disabled={!archivo || faltaSucursal || isLoading}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white hover:bg-slate-800 transition disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Cargando...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" /> Procesar Archivo
            </>
          )}
        </button>
      </form>
    </div>
  );
}
