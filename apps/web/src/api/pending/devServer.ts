import { setupWorker } from "msw/browser";

import { createProspectsHandlers } from "./prospectsHandlers";

/** Starts the browser worker with the development mock; unhandled requests go to the network. */
export async function startDevMock(): Promise<void> {
  const worker = setupWorker(...createProspectsHandlers());
  await worker.start({ onUnhandledRequest: "bypass" });
}
