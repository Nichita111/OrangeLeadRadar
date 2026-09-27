import { defineConfig } from "@playwright/test";

// Against the composed stack of docs/architecture/overview.md#runtime ("One `docker compose up`
// starts the stack locally ... The stack serves plain HTTP from `web`"): no server is started
// here, the stack must already be running (`docker compose up`) with `web` on 8080 and the
// database seeded (`docker compose exec -T api leadradar-seed-demo`).
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:8080",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
  ],
});
