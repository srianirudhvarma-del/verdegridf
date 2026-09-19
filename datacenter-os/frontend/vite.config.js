import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Phase 9: proxy API calls to the real FastAPI backend (main.py,
    // uvicorn default port 8000) instead of the frontend calling it
    // directly cross-origin. Override with VITE_BACKEND_URL for a
    // non-default backend port/host.
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  }
})
