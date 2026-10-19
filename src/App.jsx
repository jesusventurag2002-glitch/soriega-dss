import { useCallback, useState } from 'react';
import Login from './components/Login.jsx';
import Layout from './components/Layout.jsx';
import CentroDecisiones from './components/CentroDecisiones.jsx';
import TrasladosModulo, { FILTROS_INICIALES } from './components/traslados/TrasladosModulo.jsx';
import ConfiguracionInicial from './components/ConfiguracionInicial.jsx';
import PanelCapitalEstancado from './components/PanelCapitalEstancado.jsx';
import AnalisisVentas from './components/AnalisisVentas.jsx';
import ConsultaArticulos from './components/ConsultaArticulos.jsx';
import GestionLogistica from './components/GestionLogistica.jsx';
import Discrepancias from './components/Discrepancias.jsx';
import Promociones from './components/Promociones.jsx';
import Usuarios from './components/Usuarios.jsx';
import { AvisosProvider } from './components/ui/Avisos.jsx';
import { useAuth } from './auth/AuthContext.jsx';
import { puedeVer, vistaInicial } from './auth/roles.js';

// Aplicación con sesión iniciada. Se monta de nuevo con cada usuario, así nada del anterior queda en pantalla.
function Escritorio({ usuario }) {
  const { puede } = useAuth();
  const [vistaElegida, setVista] = useState(() => vistaInicial(usuario));
  // El contexto de cada módulo vive aquí para conservarse al navegar entre pantallas.
  const [filtrosTraslados, setFiltrosTraslados] = useState(FILTROS_INICIALES);
  const [detalleTraslado, setDetalleTraslado] = useState(null);
  const [sucursal, setSucursal] = useState('');

  // Una vista sin permiso nunca se renderiza, aunque se llegue a ella por un enlace o una alerta.
  const vista = puedeVer(usuario, vistaElegida) ? vistaElegida : vistaInicial(usuario);
  const cambiarVista = useCallback((id) => puedeVer(usuario, id) && setVista(id), [usuario]);

  // Desde el centro de decisiones o las alertas: abre Traslados con el filtro de la tarjeta elegida.
  const irATraslados = useCallback(
    (filtros = {}) => {
      setFiltrosTraslados({ ...FILTROS_INICIALES, ...filtros });
      setDetalleTraslado(null);
      cambiarVista('traslados');
    },
    [cambiarVista]
  );

  // Abre el detalle de un traslado conservando los filtros que ya tenía la bandeja.
  const abrirTraslado = useCallback(
    (id) => {
      setDetalleTraslado(id);
      cambiarVista('traslados');
    },
    [cambiarVista]
  );

  const ir = useCallback(
    (destino) => {
      if (typeof destino === 'string') cambiarVista(destino);
      else if (destino.vista === 'traslados') irATraslados(destino.filtros);
      else cambiarVista(destino.vista);
    },
    [cambiarVista, irATraslados]
  );

  return (
    <Layout vista={vista} onCambiarVista={cambiarVista} onIr={ir}>
      {vista === 'inicio' && (
        <CentroDecisiones
          usuario={usuario}
          sucursal={sucursal}
          onSucursal={setSucursal}
          onIrTraslados={irATraslados}
          onAbrirTraslado={abrirTraslado}
          onIr={ir}
          puedeCargar={puede('carga_datos')}
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
      {vista === 'ventas' && <AnalisisVentas onVolver={() => cambiarVista('inicio')} />}
      {vista === 'estancado' && <PanelCapitalEstancado sucursalInicial={sucursal} onAbrirTraslado={abrirTraslado} />}
      {vista === 'logistica' && <GestionLogistica />}
      {vista === 'consulta' && <ConsultaArticulos />}
      {vista === 'discrepancias' && <Discrepancias />}
      {vista === 'promociones' && <Promociones />}
      {vista === 'configuracion' && <ConfiguracionInicial />}
      {vista === 'usuarios' && <Usuarios />}
      {!vista && <p className="text-sm text-slate-600">Tu rol no tiene módulos asignados. Contacta al administrador del sistema.</p>}
    </Layout>
  );
}

export default function App() {
  const { usuario } = useAuth();
  // Con una sesión guardada se entra directamente a la aplicación, sin pasar por el login.
  if (!usuario) return <Login />;
  return (
    <AvisosProvider>
      <Escritorio key={usuario.usuario} usuario={usuario} />
    </AvisosProvider>
  );
}
