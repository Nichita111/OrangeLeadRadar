/**
 * Reads `details.fields[]` of a `VALIDATION` error ([Conventions]
 * (/architecture/interfaces.md#conventions)) into a `{field: message}` map a form can look up by
 * field name (`FR-007`).
 */
import { ApiError } from "../../../api/client";

export function fieldErrorsOf(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "VALIDATION") {
    return {};
  }
  const fields = error.details?.fields;
  if (!Array.isArray(fields)) {
    return {};
  }
  const map: Record<string, string> = {};
  for (const entry of fields) {
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    const field = (entry as Record<string, unknown>).field;
    const message = (entry as Record<string, unknown>).message;
    if (typeof field === "string" && typeof message === "string") {
      map[field] = message;
    }
  }
  return map;
}

/** The message to show outside any field: the api's message, unless every part of it was
 * already placed on a field. */
export function formLevelError(error: unknown, fieldErrors: Record<string, string>): string | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  if (error.code === "VALIDATION" && Object.keys(fieldErrors).length > 0) {
    return null;
  }
  return error.message;
}
