// The development mock of the pending contracts API-01 to API-06. Temporary: it is deleted with
// src/api/pending/ when the api's snapshot declares those paths. It reimplements no api rule beyond
// the sign-in password check of the design (G15): no lock, no disabled account, no self-change refusal.
import { createOpenApiHttp } from "openapi-msw";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
  olgaAdmin,
} from "../authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../contract";

const VARIABLE = "VITE_DEV_MOCK_PASSWORD";

/** The one development password every user of the mock signs in with; there is no default. */
export function readDevPassword(env: Record<string, unknown>): string {
  const value = env[VARIABLE];
  if (typeof value !== "string" || value === "") {
    throw new Error(
      `${VARIABLE} is not set. Set it in your shell to run the development mock, for example ${VARIABLE}=... npm run dev.`,
    );
  }
  return value;
}

const UNAUTHENTICATED = errorEnvelope("UNAUTHENTICATED", "Sign in to continue.");
const WRONG_CREDENTIALS = errorEnvelope("UNAUTHENTICATED", "The email or password is wrong.");

export function createDevHandlers(devPassword: string) {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const users: Schemas["User"][] = [{ ...anaSales }, { ...olgaAdmin }];
  let signedInId: string | null = null;

  return [
    http.post("/api/v1/auth/login", async ({ request, response }) => {
      const body = await request.json();
      const user = users.find((candidate) => candidate.email === body.email);
      if (user === undefined || body.password !== devPassword) {
        return response("default").json(WRONG_CREDENTIALS, { status: 401 });
      }
      signedInId = user.id;
      return response(200).json(authenticatedUser(user));
    }),
    http.post("/api/v1/auth/logout", ({ response }) => {
      signedInId = null;
      return response(204).empty();
    }),
    http.get("/api/v1/auth/me", ({ response }) => {
      const user = users.find((candidate) => candidate.id === signedInId);
      return user === undefined
        ? response("default").json(UNAUTHENTICATED, { status: 401 })
        : response(200).json(authenticatedUser(user));
    }),
    http.get("/api/v1/users", ({ response }) =>
      response(200).json([...users].sort((a, b) => a.display_name.localeCompare(b.display_name))),
    ),
    http.post("/api/v1/users", async ({ request, response }) => {
      const { email, display_name, role } = await request.json();
      const created: Schemas["User"] = {
        id: crypto.randomUUID(),
        email,
        display_name,
        role,
        status: "ACTIVE",
        last_login_at: null,
      };
      users.push(created);
      return response(200).json(created);
    }),
    http.patch("/api/v1/users/{id}", async ({ request, params, response }) => {
      const { display_name, role, status } = await request.json();
      const user = users.find((candidate) => candidate.id === params.id);
      if (user === undefined) {
        return response("default").json(errorEnvelope("NOT_FOUND", "The user does not exist."), {
          status: 404,
        });
      }
      if (display_name !== undefined) {
        user.display_name = display_name;
      }
      if (role !== undefined) {
        user.role = role;
      }
      if (status !== undefined) {
        user.status = status;
      }
      return response(200).json(user);
    }),
  ];
}
