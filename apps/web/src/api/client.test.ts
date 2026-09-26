// [Conventions](/architecture/interfaces.md#conventions): CSRF header on a mutating call; a
// non-2xx answer becomes an `ApiError`; `VALIDATION` field errors map by field.
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, unwrap } from "./client";
import { ApiError, fieldErrors } from "./errors";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("apiClient", () => {
  it("carries X-Requested-With on a mutating call", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.POST("/api/v1/auth/logout", {});

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("X-Requested-With")).toBe("XMLHttpRequest");
  });

  it("does not carry X-Requested-With on a GET", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(200, { id: "1", email: "a@b.c", display_name: "A", role: "SALES" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.GET("/api/v1/auth/me");

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("X-Requested-With")).toBeNull();
  });

  it("unwrap() throws an ApiError with the code and message of a non-2xx answer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(422, { error: { code: "VALIDATION", message: "The input is invalid." } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiClient.GET("/api/v1/auth/me");

    expect(() => unwrap(result)).toThrow(ApiError);
    try {
      unwrap(result);
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).code).toBe("VALIDATION");
      expect((error as ApiError).message).toBe("The input is invalid.");
    }
  });

  it("fieldErrors() maps VALIDATION details.fields by field", () => {
    const error = new ApiError(422, {
      code: "VALIDATION",
      message: "The input is invalid.",
      details: { fields: [{ field: "email", message: "is required" }] },
    });

    expect(fieldErrors(error)).toEqual({ email: "is required" });
  });
});
