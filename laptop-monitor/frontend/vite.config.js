import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend runs on a separate machine on the LAN in the real deployment
// (see ../README.md) -- set VITE_API_BASE_URL to point at it. Falls back
// to the local dev proxy target below when running everything on one
// machine for development.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8100",
        changeOrigin: true,
      },
    },
  },
});
