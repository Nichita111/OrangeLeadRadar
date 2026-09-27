import { setupWorker } from "msw/browser";

import { createAccountsAndDiscoveryHandlers } from "./accountsAndDiscovery";
import { createProspectsHandlers } from "./prospectsAndEvidence";

/** Starts the browser worker with the development mock; unhandled requests go to the network. */
export async function startDevMock(): Promise<void> {
  const worker = setupWorker(...createProspectsHandlers(), ...createAccountsAndDiscoveryHandlers());
  await worker.start({ onUnhandledRequest: "bypass" });
}
