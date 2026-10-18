import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { TONOS } from './Aviso.jsx';

const ContextoAvisos = createContext(() => {});

// Avisos emergentes: confirman qué se completó y qué sigue, o explican un error. Se apilan abajo a la derecha.
export function AvisosProvider({ children }) {
  const [avisos, setAvisos] = useState([]);
  const siguienteId = useRef(1);

  const cerrar = useCallback((id) => setAvisos((lista) => lista.filter((a) => a.id !== id)), []);

  const avisar = useCallback(
    ({ tono = 'exito', titulo, texto, accion, duracion }) => {
      const id = siguienteId.current++;
      // Como máximo 3 a la vista, para no tapar el contenido ni el panel de detalle.
      setAvisos((lista) => [...lista.slice(-2), { id, tono, titulo, texto, accion }]);
      // Los errores permanecen más tiempo para que puedan leerse con calma.
      setTimeout(() => cerrar(id), duracion ?? (tono === 'error' ? 9000 : 5000));
    },
    [cerrar]
  );

  return (
    <ContextoAvisos.Provider value={avisar}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-end gap-2 sm:left-auto sm:w-96">
        {avisos.map((a) => {
          const { icono: Icono, clase, iconoClase } = TONOS[a.tono];
          return (
            <div
              key={a.id}
              role={a.tono === 'error' ? 'alert' : 'status'}
              className={`pointer-events-auto flex w-full items-start gap-3 rounded-xl p-3.5 text-sm shadow-lg ring-1 ${clase} animate-[aparecer_150ms_ease-out]`}
            >
              <Icono className={`mt-0.5 h-4 w-4 shrink-0 ${iconoClase}`} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{a.titulo}</p>
                {a.texto && <p className="mt-0.5 opacity-90">{a.texto}</p>}
                {a.accion && (
                  <button
                    onClick={() => {
                      a.accion.onClick();
                      cerrar(a.id);
                    }}
                    className="mt-1.5 font-medium underline underline-offset-2"
                  >
                    {a.accion.texto}
                  </button>
                )}
              </div>
              <button onClick={() => cerrar(a.id)} aria-label="Cerrar aviso" className="rounded p-0.5 opacity-60 hover:opacity-100">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ContextoAvisos.Provider>
  );
}

export const useAvisos = () => useContext(ContextoAvisos);
