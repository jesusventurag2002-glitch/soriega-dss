import { useEffect, useState } from 'react';
import Boton from './Boton.jsx';
import Aviso from './Aviso.jsx';

/**
 * Confirmación de operaciones sensibles. Opcionalmente pide un texto (motivo/comentario).
 * `onConfirmar(texto)` debe devolver una promesa: si falla, el diálogo queda abierto con el error y el texto escrito.
 */
export default function Dialogo({
  titulo,
  children,
  textoConfirmar = 'Confirmar',
  varianteConfirmar = 'primario',
  campo, // { etiqueta, requerido, minimo, placeholder }
  onConfirmar,
  onCancelar,
}) {
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [errorCampo, setErrorCampo] = useState(null);

  useEffect(() => {
    const conEscape = (e) => e.key === 'Escape' && !enviando && onCancelar();
    document.addEventListener('keydown', conEscape);
    return () => document.removeEventListener('keydown', conEscape);
  }, [enviando, onCancelar]);

  const confirmar = async (e) => {
    e.preventDefault();
    if (campo?.requerido && texto.trim().length < (campo.minimo ?? 3)) {
      setErrorCampo(`Escribe al menos ${campo.minimo ?? 3} caracteres.`);
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await onConfirmar(texto.trim());
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 sm:items-center sm:p-4" onClick={() => !enviando && onCancelar()}>
      <form
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dialogo-titulo"
        onSubmit={confirmar}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:max-w-md sm:rounded-2xl"
      >
        <h2 id="dialogo-titulo" className="font-semibold text-slate-900">
          {titulo}
        </h2>
        <div className="mt-2 text-sm text-slate-600">{children}</div>

        {campo && (
          <label className="mt-4 block text-sm">
            <span className="font-medium text-slate-700">
              {campo.etiqueta}
              {!campo.requerido && <span className="font-normal text-slate-400"> (opcional)</span>}
            </span>
            <textarea
              autoFocus
              rows={3}
              value={texto}
              onChange={(e) => {
                setTexto(e.target.value);
                setErrorCampo(null);
              }}
              placeholder={campo.placeholder}
              aria-invalid={!!errorCampo}
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 ${
                errorCampo ? 'border-red-400' : 'border-slate-300'
              }`}
            />
            {errorCampo && <span className="mt-1 block text-xs text-red-700">{errorCampo}</span>}
          </label>
        )}

        {error && (
          <Aviso tono="error" className="mt-4">
            {error}
          </Aviso>
        )}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Boton onClick={onCancelar} disabled={enviando}>
            Cancelar
          </Boton>
          <Boton type="submit" variante={varianteConfirmar} cargando={enviando}>
            {textoConfirmar}
          </Boton>
        </div>
      </form>
    </div>
  );
}
