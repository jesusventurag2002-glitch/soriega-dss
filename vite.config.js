import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Accesible desde otros dispositivos de la red local (teléfono, laptop).
    host: true,
    // El navegador llama a /api en este mismo servidor y Vite lo reenvía al backend Flask,
    // que puede seguir escuchando solo en 127.0.0.1. Se usa la IP y no "localhost"
    // porque Node resuelve "localhost" a ::1 y Flask solo escucha en IPv4.
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
});
