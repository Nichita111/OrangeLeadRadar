import { defineConfig, devices } from "@playwright/test";
import { BASE_URL } from "./support/stack";

/**
 * Playwright against the composed stack (docs/guidelines/testing.md#end-to-end-tests).
 * Global setup brings the stack up once (FIXTURE_MODE=replay, seeded demo dataset) and tears
 * it down after the run; tests never substitute anything else.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  globalSetup: require.resolve("./global-setup.ts"),
  globalTeardown: require.resolve("./global-teardown.ts"),
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
