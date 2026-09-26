import { http, HttpResponse } from "msw";
import type { components } from "../../api/schema.gen";
import { users } from "../fixtures/users";
import { mockSession } from "../session";

export const authHandlers = [
  http.get("*/api/v1/auth/me", () =>
    mockSession.role === null
      ? HttpResponse.json(
          { error: { code: "UNAUTHENTICATED", message: "Sign in required." } },
          { status: 401 },
        )
      : HttpResponse.json(users[mockSession.role]),
  ),
  http.post("*/api/v1/auth/logout", () => {
    mockSession.signOut();
    return new HttpResponse(null, { status: 204 });
  }),
  http.post("*/api/v1/auth/demo-login", async ({ request }) => {
    const body = (await request.json()) as components["schemas"]["DemoLoginRequest"];
    mockSession.signIn(body.role);
    return HttpResponse.json(users[body.role]);
  }),
];
