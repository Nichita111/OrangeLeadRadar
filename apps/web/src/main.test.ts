import { expect, it, vi } from "vitest";
import { bootstrap } from "./bootstrap";
import type { ClientConfig } from "./shell/config";

const config = {
  RUN_POLL_INTERVAL_MS: 1,
  ALERT_POLL_INTERVAL_MS: 1,
  CONFIDENCE_HIGH_MIN: 0.8,
  CONFIDENCE_MEDIUM_MIN: 0.5,
  MOCK_API: true,
} satisfies ClientConfig;

it("starts the mock worker before render only when MOCK_API is true", async () => {
  const order: string[] = [];
  const startMock = vi.fn(() => {
    order.push("mock");
    return Promise.resolve();
  });
  const render = vi.fn(() => {
    order.push("render");
  });
  await bootstrap(config, startMock, render);
  expect(order).toEqual(["mock", "render"]);
  await bootstrap({ ...config, MOCK_API: false }, startMock, render);
  expect(startMock).toHaveBeenCalledTimes(1);
});
