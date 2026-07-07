import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173. VITE_API_BASE points the frontend at the FastAPI backend
// (default: the ECS deployment). Override in a local .env for localhost testing.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
