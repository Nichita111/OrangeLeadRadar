import { ApiError } from "../api/client";

export interface FormErrors {
  /** `VALIDATION` messages by form field, to show beside the field (FR-007). */
  fields: Partial<Record<string, string>>;
  /** Any other error of a save, to show as an error callout in the form (FR-007). */
  callout: string | undefined;
}

/** A field is a body field name or a JSON pointer into it; the form knows the names. */
function fieldName(field: string): string {
  return field.startsWith("/") ? field.slice(1) : field;
}

/** Splits a failed save into field errors and a callout message; nothing is dropped. */
export function formErrors(error: Error | null, formFields: readonly string[]): FormErrors {
  if (error === null) {
    return { fields: {}, callout: undefined };
  }
  if (error instanceof ApiError && error.envelope.error.code === "VALIDATION") {
    const fields: Partial<Record<string, string>> = {};
    const unplaced: string[] = [];
    for (const item of error.envelope.error.details?.fields ?? []) {
      const name = fieldName(item.field);
      if (formFields.includes(name)) {
        fields[name] = item.message;
      } else {
        unplaced.push(item.message);
      }
    }
    return { fields, callout: unplaced.length > 0 ? unplaced.join(" ") : undefined };
  }
  return { fields: {}, callout: error.message };
}
