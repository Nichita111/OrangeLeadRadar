import { setupWorker } from "msw/browser";

import { createAccountsAndDiscoveryHandlers } from "./accountsAndDiscovery";
import { createAccountsAndRunsHandlers } from "./accountsAndRuns";
import { createAlertsHandlers } from "./alerts";
import { createAuthenticationHandlers } from "./authentication";
import { createOutreachAndCrmHandlers } from "./outreachAndCrm";
import { createProspectsHandlers } from "./prospectsAndEvidence";
import { createMockStore } from "./store";

/** Starts the browser worker with the development mock; unhandled requests go to the network. */
export async function startDevMock(): Promise<void> {
  const store = createMockStore();
  const worker = setupWorker(
    ...createAuthenticationHandlers(),
    ...createAccountsAndRunsHandlers(store),
    ...createProspectsHandlers(store),
    ...createAccountsAndDiscoveryHandlers(store),
    ...createOutreachAndCrmHandlers(store),
    ...createAlertsHandlers(store),
  );
  // Every mocked answer may have changed the store, so it is kept after each one.
  worker.events.on("response:mocked", () => {
    store.save();
  });
  await worker.start({ onUnhandledRequest: "bypass" });
}
