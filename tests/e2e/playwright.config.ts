import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  fullyParallel: true,
  use: {
    baseURL: process.env.WEB_BASE_URL ?? "http://127.0.0.1:8080",
    channel: "chrome",
    trace: "retain-on-failure",
  },
});
