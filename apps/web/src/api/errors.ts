import type { components } from "./schema.gen";

type ErrorBody = components["schemas"]["ErrorBody"];

/**
 * A non-2xx answer of [Conventions](/architecture/interfaces.md#conventions), typed from the
 * generated `ErrorBody`.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorBody["details"];

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

/**
 * Maps a `VALIDATION` error's `details.fields[]`
 * ([Conventions](/architecture/interfaces.md#conventions)) by field name, for
 * [`FormField`](../shell/FormField.tsx).
 */
export function fieldErrors(error: ApiError): Record<string, string> {
  if (error.code !== "VALIDATION" || error.details === null || error.details === undefined) {
    return {};
  }
  const fields = (error.details as Record<string, unknown>).fields;
  if (!Array.isArray(fields)) {
    return {};
  }
  const entries = fields.filter(
    (entry): entry is { field: string; message: string } =>
      typeof entry === "object" &&
      entry !== null &&
      typeof (entry as Record<string, unknown>).field === "string" &&
      typeof (entry as Record<string, unknown>).message === "string",
  );
  return Object.fromEntries(entries.map((entry) => [entry.field, entry.message]));
}
