import { afterEach } from "vitest";

import { anaSales, olgaAdmin } from "../../api/authenticationAndUsers.fixtures";
import { createProspectsHandlers } from "../../api/pending/prospectsHandlers";
import { renderApp, signedInAs } from "../../testRender";
import { server } from "../../testServer";

const requested: string[] = [];
server.events.on("request:start", ({ request }) => {
  requested.push(request.url);
});
afterEach(() => {
  requested.length = 0;
  localStorage.clear();
});

/** The URLs the client requested during the current test. */
export function requestedUrls(): string[] {
  return [...requested];
}

/** Renders the client at `path`, signed in as the Admin or a Sales user, with the Prospects mock. */
export function renderAt(path: string, role: "ADMIN" | "SALES" = "ADMIN") {
  server.use(...createProspectsHandlers());
  signedInAs(role === "ADMIN" ? olgaAdmin : anaSales);
  return renderApp(path);
}
