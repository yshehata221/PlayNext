import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // GitHub Pages serves a project site from /<repo>/, so assets need that
  // prefix. Set BASE_PATH=/playnext/ in the Pages workflow; everywhere else
  // (local dev, Render, Netlify) it stays at the root.
  base: process.env.BASE_PATH ?? "/",
  plugins: [react()],
  server: {
    port: 5173,
    // everything under /api goes to FastAPI so the browser never deals with CORS
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
