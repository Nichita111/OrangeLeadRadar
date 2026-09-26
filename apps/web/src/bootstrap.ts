import type { ClientConfig } from "./shell/config";

/** Starts the mock layer before the first render, and only when runtime config enables it. */
export async function bootstrap(
  config: ClientConfig,
  startMock: () => Promise<void>,
  render: () => void,
): Promise<void> {
  if (config.MOCK_API) await startMock();
  render();
}
