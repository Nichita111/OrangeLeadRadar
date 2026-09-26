/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The `web` container's own proxy of `/api/v1` to `API_UPSTREAM` is `templates/default.conf.template`
// (nginx, in production). `publicDir` holds the development mock's worker script and `config.json`
// for `serve` only, so a production build never copies them into `dist`.
export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  publicDir: command === "serve" ? "dev-public" : false,
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
}));
