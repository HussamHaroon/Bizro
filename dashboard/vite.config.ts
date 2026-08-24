import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Vite config — hand-scaffolded per bizro-frontend-agent SKILL.md (no interactive create-vite).
// Dev proxy: when the backend (server/) is live on :8000, /api and /webhook hit it directly.
// Set VITE_API_BASE_URL to point the typed client at a deployed server instead of mocks.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000';
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/webhook': { target: apiTarget, changeOrigin: true },
      },
    },
  };
});
