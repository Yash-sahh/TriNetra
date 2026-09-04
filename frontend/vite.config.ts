import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Keep the browser on one origin during local development. Without this proxy
// a request to `/api/*` reaches Vite (5173) rather than FastAPI (8000), which
// manifests in the sign-in screen as the generic "Request failed" message.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
