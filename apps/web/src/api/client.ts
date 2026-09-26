/**
 * The one client every capability's hooks call through: sends `X-Requested-With` and credentials
 * on every request, and maps the error envelope of
 * [Conventions](/architecture/interfaces.md#conventions) — `{"error": {"code", "message",
 * "details"?}}` — which is not a named shape of `schema.gen.ts` (FastAPI documents only its
 * automatic `422`; every other status is raised through an exception handler, never a declared
 * response model, so `openapi-typescript` never sees it). `ApiError` is this file's one hand-kept
 * copy of that wire convention, not of a contract shape.
 */

const BASE_PATH = "/api/v1";

export interface ApiErrorDetails {
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetails | undefined;

  constructor(status: number, code: string, message: string, details?: ApiErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: ApiErrorDetails;
  };
}

/** Set by the shell once it can navigate ([FR-006](/architecture/services/frontend.md#states)); a
 * request that opts out (the login attempt itself) never triggers it. */
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** False for the login attempt: a `401` there is an expected outcome shown inline, never a
   * redirect ([FR-094](/features/identity-and-access.md#sign-in)). */
  redirectOnUnauthorized?: boolean;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { "X-Requested-With": "XMLHttpRequest" };
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    if (options.body instanceof FormData) {
      // `API-22`'s multipart upload: the browser sets its own boundary `Content-Type`.
      body = options.body;
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(`${BASE_PATH}${path}`, {
    method,
    headers,
    credentials: "include",
    ...(body !== undefined ? { body } : {}),
    ...(options.signal !== undefined ? { signal: options.signal } : {}),
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await parseBody(response);

  if (!response.ok) {
    if (response.status === 401 && options.redirectOnUnauthorized !== false) {
      unauthorizedHandler?.();
    }
    const envelope = data as ErrorEnvelope | null;
    throw new ApiError(
      response.status,
      envelope?.error?.code ?? "INTERNAL",
      envelope?.error?.message ?? response.statusText,
      envelope?.error?.details,
    );
  }

  return data as T;
}
