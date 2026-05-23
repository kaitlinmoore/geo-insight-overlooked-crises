import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Dev server proxies /api to the FastAPI backend (see server/README note).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    // react-map-gl's pre-bundled chunk otherwise links its own React copy,
    // tripping "Invalid hook call / two copies of React" at runtime.
    dedupe: ["react", "react-dom"],
  },
  optimizeDeps: {
    include: ["react-map-gl/maplibre", "maplibre-gl"],
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
