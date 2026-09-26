import { HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { errorEnvelope } from "./authenticationAndUsers.fixtures";
import { ApiError, client, parseErrorEnvelope } from "./client";
import { http, server } from "../testServer";

describe("api client", () => {
  it("Conventions: sends X-Requested-With on POST and PATCH", async () => {
    const seen: (string | null)[] = [];
    server.use(
      http.post("/api/v1/auth/logout", ({ request, response }) => {
        seen.push(request.headers.get("X-Requested-With"));
        return response(204).empty();
      }),
      http.patch("/api/v1/users/{id}", ({ request, response }) => {
        seen.push(request.headers.get("X-Requested-With"));
        return response(200).json({
          id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a1a01",
          email: "a@b.c",
          display_name: "A",
          role: "SALES",
          status: "ACTIVE",
          last_login_at: null,
        });
      }),
    );
    await client.POST("/api/v1/auth/logout");
    await client.PATCH("/api/v1/users/{id}", {
      params: { path: { id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a1a01" } },
      body: { display_name: "A" },
    });
    expect(seen).toEqual(["XMLHttpRequest", "XMLHttpRequest"]);
  });

  it("Conventions: an envelope parses into ApiError with the status", async () => {
    const envelope = errorEnvelope("LOCKED", "Locked for 5 minutes.", { retry_after_min: 5 });
    server.use(
      http.get("/api/v1/auth/me", ({ response }) =>
        response("default").json(envelope, { status: 423 }),
      ),
    );
    const failure = await client.GET("/api/v1/auth/me").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(423);
    expect((failure as ApiError).envelope).toEqual(envelope);
  });

  it("Conventions: a body that is not an envelope throws with the status", async () => {
    server.use(
      http.untyped.get(`${window.location.origin}/api/v1/auth/me`, () =>
        HttpResponse.text("<html>bad gateway</html>", { status: 502 }),
      ),
    );
    const failure = await client.GET("/api/v1/auth/me").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(Error);
    expect(failure).not.toBeInstanceOf(ApiError);
    expect((failure as Error).message).toContain("502");
  });

  it("a malformed field error makes the body a non-envelope, never a shorter list", () => {
    expect(
      parseErrorEnvelope({
        error: {
          code: "VALIDATION",
          message: "Invalid.",
          details: { fields: [{ field: "/email", message: "Bad." }, { field: "/role" }] },
        },
      }),
    ).toBeNull();
  });
});
