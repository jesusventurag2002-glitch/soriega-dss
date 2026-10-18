import { useCallback, useState } from 'react';
import Login from './components/Login.jsx';
import Layout from './components/Layout.jsx';
import CentroDecisiones from './components/CentroDecisiones.jsx';
import TrasladosModulo, { FILTROS_INICIALES } from './components/traslados/TrasladosModulo.jsx';
import ConfiguracionInicial from './components/ConfiguracionInicial.jsx';
import PanelCapitalEstancado from './components/PanelCapitalEstancado.jsx';
import AnalisisVentas from './components/AnalisisVentas.jsx';
import { AvisosProvider } from './components/ui/Avisos.jsx';
import { USUARIOS } from './data/mockData.js';
import { establecerUsuario } from './services/api.js';

export default function App() {
  const [usuario, setUsuario] = useState(null);
  const [vista, setVista] = useState('inicio');
  // El contexto de cada módulo vive aquí para conservarse al navegar entre pantallas.
  const [filtrosTraslados, setFiltrosTraslados] = useState(FILTROS_INICIALES);
  const [detalleTraslado, setDetalleTraslado] = useState(null);
  const [sucursal, setSucursal] = useState('');

  const iniciarSesion = (rol) => {
    establecerUsuario(USUARIOS[rol]);
    setUsuario(USUARIOS[rol]);
  };

  const cerrarSesion = () => {
    establecerUsuario(null);
    setUsuario(null);
    setVista('inicio');
    setFiltrosTraslados(FILTROS_INICIALES);
    setDetalleTraslado(null);
    setSucursal('');
  };

  // Desde el centro de decisiones o las alertas: abre Traslados con el filtro de la tarjeta elegida.
  const irATraslados = useCallback((filtros = {}) => {
    setFiltrosTraslados({ ...FILTROS_INICIALES, ...filtros });
    setDetalleTraslado(null);
    setVista('traslados');
  }, []);

  // Abre el detalle de un traslado conservando los filtros que ya tenía la bandeja.
  const abrirTraslado = useCallback((id) => {
    setDetalleTraslado(id);
    setVista('traslados');
  }, []);

  const ir = useCallback(
    (destino) => {
      if (typeof destino === 'string') setVista(destino);
      else if (destino.vista === 'traslados') irATraslados(destino.filtros);
      else setVista(destino.vista);
    },
    [irATraslados]
  );

  if (!usuario) {
    return <Login onLogin={iniciarSesion} />;
  }

  return (
    <AvisosProvider>
      <Layout usuario={usuario} vista={vista} onCambiarVista={setVista} onIr={ir} onLogout={cerrarSesion}>
        {vista === 'inicio' && (
          <CentroDecisiones
            usuario={usuario}
            sucursal={sucursal}
            onSucursal={setSucursal}
            onIrTraslados={irATraslados}
            onAbrirTraslado={abrirTraslado}
            onIr={ir}
          />
        )}
        {vista === 'traslados' && (
          <TrasladosModulo
            filtros={filtrosTraslados}
            onFiltros={setFiltrosTraslados}
            detalleId={detalleTraslado}
            onDetalle={setDetalleTraslado}
          />
        )}
        {vista === 'ventas' && <AnalisisVentas onVolver={() => setVista('inicio')} />}
        {vista === 'estancado' && <PanelCapitalEstancado sucursalInicial={sucursal} onAbrirTraslado={abrirTraslado} />}
        {vista === 'configuracion' && <ConfiguracionInicial />}
      </Layout>
    </AvisosProvider>
  );
}
