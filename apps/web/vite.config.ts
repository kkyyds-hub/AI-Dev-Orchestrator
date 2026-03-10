import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
  const proxyConfig = {
    "/health": {
      target: backendTarget,
      changeOrigin: true,
    },
    "/tasks": {
      target: backendTarget,
      changeOrigin: true,
    },
    "/workers": {
      target: backendTarget,
      changeOrigin: true,
    },
  };

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: proxyConfig,
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      proxy: proxyConfig,
    },
  };
});
