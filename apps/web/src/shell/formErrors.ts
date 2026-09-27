import { ApiError } from "../api/client";

export interface FormErrors {
  /** `VALIDATION` messages by form field, to show beside the field (FR-007). */
  fields: Partial<Record<string, string>>;
  /** Any other error of a save, to show as an error callout in the form (FR-007). */
  callout: string | undefined;
}

/** A field is a body field name or a JSON pointer into it; the form knows the names. */
function normalized(field: string): string {
  return field.startsWith("/") ? field.slice(1) : field;
}

/** True when `pointer` names `formField` itself, or a key underneath it (a `/`-bounded prefix). */
function namesOrIsUnder(pointer: string, formField: string): boolean {
  return pointer === formField || pointer.startsWith(`${formField}/`);
}

/**
 * Splits a failed save into field errors and a callout message; nothing is dropped. A
 * `VALIDATION` field is placed on the longest registered form field that names it or a key
 * underneath it (FR-034): a flat form's exact field names behave exactly as before, and a nested
 * form's pointer (`/icp_criteria/2/values`) catches every error inside that criterion unless a
 * more specific pointer is also registered. Several messages landing on the same field are kept,
 * not overwritten.
 */
export function formErrors(error: Error | null, formFields: readonly string[]): FormErrors {
  if (error === null) {
    return { fields: {}, callout: undefined };
  }
  if (error instanceof ApiError && error.envelope.error.code === "VALIDATION") {
    const fields: Partial<Record<string, string>> = {};
    const unplaced: string[] = [];
    for (const item of error.envelope.error.details?.fields ?? []) {
      const pointer = normalized(item.field);
      let longest: string | undefined;
      for (const formField of formFields) {
        if (
          namesOrIsUnder(pointer, normalized(formField)) &&
          (longest === undefined || formField.length > longest.length)
        ) {
          longest = formField;
        }
      }
      if (longest === undefined) {
        unplaced.push(item.message);
      } else {
        const existing = fields[longest];
        fields[longest] = existing === undefined ? item.message : `${existing} ${item.message}`;
      }
    }
    return { fields, callout: unplaced.length > 0 ? unplaced.join(" ") : undefined };
  }
  return { fields: {}, callout: error.message };
}
