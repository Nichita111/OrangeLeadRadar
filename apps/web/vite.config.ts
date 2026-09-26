/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The `web` container's own proxy of `/api/v1` to `API_UPSTREAM` is `templates/default.conf.template`
// (nginx, in production). Component tests never call the network
// (`docs/guidelines/typescript.md#tests`), so this config carries no dev proxy.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
