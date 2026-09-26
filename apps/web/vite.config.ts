/// <reference types="vitest/config" />
import { execFileSync } from "node:child_process";
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

// [frontend Design](/architecture/services/frontend.md#design): the `web` container writes
// `/config.json` from the environment when it starts; in dev, this plugin runs the same script
// (`docker/config-json.sh`) to answer the same path, so there is one place holding the defaults.
function configJsonPlugin(): Plugin {
  return {
    name: "leadradar-config-json",
    configureServer(server) {
      server.middlewares.use("/config.json", (_req, res) => {
        const output = execFileSync(
          "sh",
          [path.resolve(import.meta.dirname, "docker/config-json.sh")],
          {
            env: process.env,
          },
        );
        res.setHeader("content-type", "application/json");
        res.end(output);
      });
    },
  };
}

// The `web` container's own proxy of `/api/v1` to `API_UPSTREAM` is `templates/default.conf.template`
// (nginx, in production); in dev the same proxy is enabled only when `API_UPSTREAM` is set, so
// the shell can also run against MSW alone with no api present.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react(), tailwindcss(), configJsonPlugin()],
    server: {
      proxy: env.API_UPSTREAM
        ? { "/api/v1": { target: env.API_UPSTREAM, changeOrigin: true } }
        : undefined,
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/setupTests.ts"],
    },
  };
});
