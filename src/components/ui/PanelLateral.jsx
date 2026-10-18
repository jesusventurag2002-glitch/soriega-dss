import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

// Panel lateral para consultar el detalle de un registro sin salir de la lista. En móvil ocupa toda la pantalla.
export default function PanelLateral({ abierto, titulo, subtitulo, onCerrar, children, ancho = 'sm:max-w-xl' }) {
  const botonCerrar = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;
    botonCerrar.current?.focus();
    const conEscape = (e) => e.key === 'Escape' && onCerrar();
    document.addEventListener('keydown', conEscape);
    return () => document.removeEventListener('keydown', conEscape);
  }, [abierto, onCerrar]);

  if (!abierto) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onClick={onCerrar}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={typeof titulo === 'string' ? titulo : undefined}
        onClick={(e) => e.stopPropagation()}
        className={`flex h-full w-full flex-col bg-white shadow-2xl ${ancho} animate-[deslizar_180ms_ease-out]`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <div className="font-semibold text-slate-900">{titulo}</div>
            {subtitulo && <div className="mt-0.5 text-sm text-slate-500">{subtitulo}</div>}
          </div>
          <button
            ref={botonCerrar}
            onClick={onCerrar}
            aria-label="Cerrar panel"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </aside>
    </div>
  );
}
