import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Development-only reverse proxy. Production serves FastAPI and React under one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/files': 'http://127.0.0.1:18130',
      '/health': 'http://127.0.0.1:18130',
      '/docs': 'http://127.0.0.1:18130',
      '/openapi.json': 'http://127.0.0.1:18130',
    },
  },
});
