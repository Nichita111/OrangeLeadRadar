import createClient, { type Middleware } from "openapi-fetch";

import type { Schemas, paths } from "./contract";
import { isDependency } from "./dependencies";

type ErrorEnvelope = Schemas["ErrorEnvelope"];

/** A non-2xx answer of the api, parsed from the envelope of Conventions. */
export class ApiError extends Error {
  readonly status: number;
  readonly envelope: ErrorEnvelope;

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.error.message);
    this.name = "ApiError";
    this.status = status;
    this.envelope = envelope;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseDetails(value: unknown): ErrorEnvelope["error"]["details"] | null {
  if (!isRecord(value)) {
    return null;
  }
  const details: NonNullable<ErrorEnvelope["error"]["details"]> = {};
  const { fields, entity_id, retry_after_min, resets_at, dependency, reason } = value;
  if (Array.isArray(fields)) {
    const parsed: { field: string; message: string }[] = [];
    for (const item of fields as unknown[]) {
      if (
        !isRecord(item) ||
        typeof item["field"] !== "string" ||
        typeof item["message"] !== "string"
      ) {
        // A malformed field error is a body that is not an envelope, never a silently shorter list.
        return null;
      }
      parsed.push({ field: item["field"], message: item["message"] });
    }
    details.fields = parsed;
  }
  if (typeof entity_id === "string") {
    details.entity_id = entity_id;
  }
  if (typeof retry_after_min === "number") {
    details.retry_after_min = retry_after_min;
  }
  if (typeof resets_at === "string") {
    details.resets_at = resets_at;
  }
  if (isDependency(dependency)) {
    // A value outside Dependencies names no Degradation row: the error shows its message.
    details.dependency = dependency;
  }
  if (typeof reason === "string") {
    details.reason = reason;
  }
  return details;
}

/** Parses a body into the envelope; null when the body is not one. */
export function parseErrorEnvelope(body: unknown): ErrorEnvelope | null {
  if (!isRecord(body) || !isRecord(body["error"])) {
    return null;
  }
  const { code, message, details } = body["error"];
  if (typeof code !== "string" || typeof message !== "string") {
    return null;
  }
  const parsed = details === undefined ? undefined : parseDetails(details);
  if (parsed === null) {
    return null;
  }
  return { error: parsed === undefined ? { code, message } : { code, message, details: parsed } };
}

const middleware: Middleware = {
  onRequest({ request }) {
    request.headers.set("X-Requested-With", "XMLHttpRequest");
    return request;
  },
  async onResponse({ response }) {
    if (response.ok) {
      return undefined;
    }
    const body: unknown = await response
      .clone()
      .json()
      .catch(() => null);
    const envelope = parseErrorEnvelope(body);
    if (envelope === null) {
      throw new Error(`The api answered ${String(response.status)} without an error envelope.`);
    }
    throw new ApiError(response.status, envelope);
  },
};

// The path keys carry `/api/v1`, so the base is the origin (Node's fetch refuses relative URLs).
export const client = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "same-origin",
  // Resolved at call time, so a fetch installed after this module loads (the tests' MSW) is used.
  fetch: (request) => fetch(request),
});
client.use(middleware);

/** A 2xx answer with a body always carries data; anything else is a defect, never a fallback. */
export function requireData<T>(data: T | undefined): T {
  if (data === undefined) {
    throw new Error("The api answered without a body.");
  }
  return data;
}
