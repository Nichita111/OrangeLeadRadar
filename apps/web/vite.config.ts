/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The `web` container's own proxy of `/api/v1` to `API_UPSTREAM` is `templates/default.conf.template`
// (nginx, in production); this config has no dev proxy because no screen calls the api yet.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
