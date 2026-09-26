import createClient from "openapi-fetch";

import { ApiError } from "./errors";
import type { components, paths } from "./schema.gen";

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * The typed client of [Conventions](/architecture/interfaces.md#conventions): same-origin
 * credentials (the session cookie), and `X-Requested-With` on every mutating request (CSRF).
 * The base is an absolute URL built from the current origin: the underlying `Request` object
 * cannot resolve a relative one without a document to resolve it against.
 */
export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // Resolves `fetch` at call time, not at client creation: `openapi-fetch` otherwise binds
  // `globalThis.fetch` once, which a test's `vi.stubGlobal("fetch", ...)` (run after this module
  // is imported) would then never reach.
  fetch: (input: Request) => globalThis.fetch(input),
});

apiClient.use({
  onRequest({ request }) {
    if (MUTATING_METHODS.has(request.method)) {
      request.headers.set("X-Requested-With", "XMLHttpRequest");
    }
    return request;
  },
});

interface ClientResult<T> {
  data?: T;
  error?: components["schemas"]["ErrorEnvelope"];
  response: Response;
}

/**
 * Turns an `openapi-fetch` `{data, error}` result into its data, or throws the `error` as a typed
 * `ApiError` ([Conventions](/architecture/interfaces.md#conventions)).
 */
export function unwrap<T>(result: ClientResult<T>): T {
  throwIfError(result);
  if (result.data === undefined) {
    throw new ApiError(result.response.status, {
      code: "INTERNAL",
      message: "The api answered with no body.",
    });
  }
  return result.data;
}

/** Accepts a successful no-content contract such as `API-02`, while preserving typed errors. */
export function unwrapNoContent(result: ClientResult<unknown>): void {
  throwIfError(result);
}

function throwIfError(result: ClientResult<unknown>): void {
  if (result.error) {
    throw new ApiError(result.response.status, result.error.error);
  }
}
