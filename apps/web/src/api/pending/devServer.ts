import { setupWorker } from "msw/browser";

import { createDevHandlers, readDevPassword } from "./devHandlers";

/** Starts the browser worker with the development mock; unhandled requests go to the network. */
export async function startDevMock(env: Record<string, unknown>): Promise<void> {
  const worker = setupWorker(...createDevHandlers(readDevPassword(env)));
  await worker.start({ onUnhandledRequest: "bypass" });
}
