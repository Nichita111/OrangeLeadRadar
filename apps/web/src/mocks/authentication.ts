// The development mock of Sign in (`API-01` to `API-03`, `API-78`), so the screens behind the
// session open without the api (TypeScript Mock layer). Temporary: the session is the signed-in
// user's id kept in `sessionStorage`, so a reload keeps it and a new tab starts signed out; the
// two demo dataset users sign in with any non-empty password; there is no lockout.
import { createOpenApiHttp } from "openapi-msw";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
  errorResponse,
  olgaAdmin,
} from "../api/authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../api/contract";

const SESSION_KEY = "leadradar-mock-session";
const USERS: Schemas["User"][] = [anaSales, olgaAdmin];

function readSession(): Schemas["User"] | undefined {
  try {
    const id = sessionStorage.getItem(SESSION_KEY);
    return USERS.find((user) => user.id === id);
  } catch {
    return undefined;
  }
}

function writeSession(user: Schemas["User"] | undefined): void {
  try {
    if (user === undefined) {
      sessionStorage.removeItem(SESSION_KEY);
    } else {
      sessionStorage.setItem(SESSION_KEY, user.id);
    }
  } catch {
    // Storage blocked: the session then lasts until the page reloads, as the in-memory cache does.
  }
}

/** The signed-in user of the mock, for handlers that record who did something. */
export function mockSessionUser(): Schemas["User"] {
  return readSession() ?? olgaAdmin;
}

export function createAuthenticationHandlers() {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const unauthenticated = () =>
    errorResponse(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), 401);

  return [
    http.get("/api/v1/auth/me", ({ response }) => {
      const user = readSession();
      return user === undefined ? unauthenticated() : response(200).json(authenticatedUser(user));
    }),
    http.post("/api/v1/auth/login", async ({ request, response }) => {
      const body = await request.json();
      const user = USERS.find((candidate) => candidate.email === body.email.trim().toLowerCase());
      if (user === undefined || body.password === "") {
        return errorResponse(
          errorEnvelope("UNAUTHENTICATED", "The email or password is wrong."),
          401,
        );
      }
      writeSession(user);
      return response(200).json(authenticatedUser(user));
    }),
    http.post("/api/v1/auth/demo-login", async ({ request, response }) => {
      const body = await request.json();
      const user = body.role === "ADMIN" ? olgaAdmin : anaSales;
      writeSession(user);
      return response(200).json(authenticatedUser(user));
    }),
    http.post("/api/v1/auth/logout", ({ response }) => {
      if (readSession() === undefined) {
        return unauthenticated();
      }
      writeSession(undefined);
      return response(204).empty();
    }),
  ];
}
