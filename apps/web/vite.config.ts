import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import type { IncomingMessage } from "node:http";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
  const proxyPrefixes = [
    "/health",
    "/tasks",
    "/workers",
    "/console",
    "/strategy",
    "/projects",
    "/roles",
    "/skills",
    "/provider-settings",
    "/planning",
    "/deliverables",
    "/approvals",
    "/runs",
    "/repositories",
    "/events",
    "/agent-threads",
  ];
  const proxyConfig = Object.fromEntries(
    proxyPrefixes.map((prefix) => [
      prefix,
      {
        target: backendTarget,
        changeOrigin: true,
        bypass: (req: IncomingMessage) => {
          const accept = req.headers.accept ?? "";
          if (req.method === "GET" && accept.includes("text/html")) {
            return req.url;
          }
          return undefined;
        },
      },
    ]),
  );

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
