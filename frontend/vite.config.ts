import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { input: ["index.html", "services/api-trading/index.html"] } },
  server: {
    proxy: {
      "/ws": { target: "ws://localhost:8000", ws: true }, "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
