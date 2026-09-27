import { afterEach } from "vitest";

import {
  anaSales,
  errorEnvelope,
  errorResponse,
  olgaAdmin,
} from "../../api/authenticationAndUsers.fixtures";
import { createProspectsHandlers } from "../../mocks/prospectsAndEvidence";
import {
  accounts,
  industries,
  markets,
  scoringConfig,
  scoringSummaries,
  services,
} from "../../mocks/prospectsAndEvidence.fixtures";
import { renderApp, signedInAs } from "../../testRender";
import { http, server } from "../../testServer";

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
  const notFound = errorEnvelope("NOT_FOUND", "Not found.");
  server.use(
    ...createProspectsHandlers(),
    http.get("/api/v1/services", ({ response }) => response(200).json(services)),
    http.get("/api/v1/industries", ({ response }) => response(200).json(industries)),
    http.get("/api/v1/markets", ({ response }) => response(200).json(markets)),
    http.get("/api/v1/services/{id}/scoring-configs", ({ params, response }) =>
      response(200).json(params.id === "svc-1" ? scoringSummaries : []),
    ),
    http.get("/api/v1/scoring-configs/{id}", ({ params, response }) =>
      params.id === scoringConfig.id
        ? response(200).json(scoringConfig)
        : errorResponse(notFound, 404),
    ),
    http.get("/api/v1/accounts/{id}", ({ params, response }) => {
      const account = accounts.find((item) => item.id === params.id);
      return account === undefined ? errorResponse(notFound, 404) : response(200).json(account);
    }),
  );
  signedInAs(role === "ADMIN" ? olgaAdmin : anaSales);
  return renderApp(path);
}
