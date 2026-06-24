import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config. The dev server proxies nothing — the frontend calls the backend
// directly via VITE_API_BASE_URL (see .env.example), so it works identically in
// local dev and when deployed as a static site.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
