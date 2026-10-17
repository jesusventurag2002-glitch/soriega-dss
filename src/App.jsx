import { useState } from 'react';
import Login from './components/Login.jsx';
import Layout from './components/Layout.jsx';
import Dashboard from './components/Dashboard.jsx';
import { USUARIOS } from './data/mockData.js';

export default function App() {
  const [usuario, setUsuario] = useState(null);

  if (!usuario) {
    return <Login onLogin={(rol) => setUsuario(USUARIOS[rol])} />;
  }

  return (
    <Layout usuario={usuario} onLogout={() => setUsuario(null)}>
      <Dashboard usuario={usuario} />
    </Layout>
  );
}
