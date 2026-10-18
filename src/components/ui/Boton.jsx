import { Loader2 } from 'lucide-react';

const VARIANTES = {
  primario: 'bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-300',
  secundario: 'bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100 disabled:text-slate-400',
  peligro: 'bg-white text-red-700 ring-1 ring-red-200 hover:bg-red-50 disabled:text-red-300',
  exito: 'bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-300',
  fantasma: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:text-slate-300',
};

const TAMANOS = {
  sm: 'gap-1.5 px-2.5 py-1.5 text-xs',
  md: 'gap-2 px-4 py-2 text-sm',
};

// Botón común. Mientras `cargando` está activo muestra un indicador y no acepta otro clic.
export default function Boton({
  variante = 'secundario',
  tamano = 'md',
  icono: Icono,
  cargando = false,
  disabled,
  className = '',
  children,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      className={`inline-flex items-center justify-center whitespace-nowrap rounded-lg font-medium transition disabled:cursor-not-allowed ${VARIANTES[variante]} ${TAMANOS[tamano]} ${className}`}
      {...props}
    >
      {cargando ? (
        <Loader2 className={`${tamano === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} animate-spin`} />
      ) : (
        Icono && <Icono className={`${tamano === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} shrink-0`} />
      )}
      {children}
    </button>
  );
}
