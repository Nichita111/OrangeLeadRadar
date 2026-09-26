import { render } from "@testing-library/react";
import { createMemoryRouter } from "react-router";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
  errorResponse,
} from "./api/authenticationAndUsers.fixtures";
import type { Schemas } from "./api/contract";
import { App } from "./App";
import type { Config } from "./config";
import { routes } from "./router";
import { http, server } from "./testServer";

export const testConfig: Config = { CONFIDENCE_HIGH_MIN: 0.85, CONFIDENCE_MEDIUM_MIN: 0.65 };

/** Renders the whole client at a route, with the routes of the router and an in-memory history. */
export function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const view = render(<App config={testConfig} router={router} />);
  return { router, ...view };
}

/** Arranges `API-03` to answer with the signed-in user. */
export function signedInAs(user: Schemas["User"] = anaSales): void {
  server.use(
    http.get("/api/v1/auth/me", ({ response }) => response(200).json(authenticatedUser(user))),
  );
}

/** Arranges `API-03` to answer `401`, as it does for a visitor with no session. */
export function anonymous(): void {
  server.use(
    http.get("/api/v1/auth/me", () =>
      errorResponse(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), 401),
    ),
  );
}
