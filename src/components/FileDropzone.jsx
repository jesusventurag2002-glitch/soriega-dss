import { useRef, useState } from 'react';
import { UploadCloud, FileSpreadsheet, X } from 'lucide-react';

const EXTENSIONES = ['.xlsx', '.xls', '.csv'];

const formatearTamano = (bytes) =>
  bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(2)} MB`;

const esValido = (archivo) => EXTENSIONES.some((ext) => archivo.name.toLowerCase().endsWith(ext));

export default function FileDropzone({ archivo, onSeleccionar, onError, deshabilitado }) {
  const [arrastrando, setArrastrando] = useState(false);
  const inputRef = useRef(null);

  const seleccionar = (nuevo) => {
    if (!nuevo) return;
    if (!esValido(nuevo)) {
      onError(`Formato no permitido. Usa ${EXTENSIONES.join(', ')}.`);
      return;
    }
    onSeleccionar(nuevo);
  };

  const quitar = () => {
    onSeleccionar(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  if (archivo) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <div className="h-11 w-11 shrink-0 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <FileSpreadsheet className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900">{archivo.name}</p>
          <p className="text-xs text-slate-500">{formatearTamano(archivo.size)}</p>
        </div>
        <button
          type="button"
          onClick={quitar}
          disabled={deshabilitado}
          title="Quitar archivo"
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-200 hover:text-slate-900 transition disabled:opacity-50"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setArrastrando(true);
      }}
      onDragLeave={() => setArrastrando(false)}
      onDrop={(e) => {
        e.preventDefault();
        setArrastrando(false);
        seleccionar(e.dataTransfer.files[0]);
      }}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${
        arrastrando ? 'border-slate-900 bg-slate-100' : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50'
      }`}
    >
      <div className="h-12 w-12 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center mb-3">
        <UploadCloud className="h-6 w-6" />
      </div>
      <p className="text-sm font-medium text-slate-900">
        Arrastra tu archivo aquí o <span className="text-slate-900 underline underline-offset-2">selecciónalo</span>
      </p>
      <p className="mt-1 text-xs text-slate-500">Formatos aceptados: {EXTENSIONES.join(', ')}</p>
      <input
        ref={inputRef}
        type="file"
        accept={EXTENSIONES.join(',')}
        className="sr-only"
        onChange={(e) => seleccionar(e.target.files[0])}
      />
    </label>
  );
}
