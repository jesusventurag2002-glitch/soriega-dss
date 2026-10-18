import { useState } from 'react';
import Login from './components/Login.jsx';
import Layout from './components/Layout.jsx';
import Dashboard from './components/Dashboard.jsx';
import ConfiguracionInicial from './components/ConfiguracionInicial.jsx';
import { USUARIOS } from './data/mockData.js';

export default function App() {
  const [usuario, setUsuario] = useState(null);
  const [vista, setVista] = useState('dashboard');

  if (!usuario) {
    return <Login onLogin={(rol) => setUsuario(USUARIOS[rol])} />;
  }

  return (
    <Layout
      usuario={usuario}
      vista={vista}
      onCambiarVista={setVista}
      onLogout={() => {
        setUsuario(null);
        setVista('dashboard');
      }}
    >
      {vista === 'dashboard' ? <Dashboard usuario={usuario} /> : <ConfiguracionInicial />}
    </Layout>
  );
}
