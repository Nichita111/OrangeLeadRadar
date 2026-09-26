import { describe, expect, it } from "vitest";

import { errorEnvelope } from "../api/authenticationAndUsers.fixtures";
import { ApiError } from "../api/client";
import { formErrors } from "./formErrors";

const fieldsOfForm = ["email", "password"];

describe("formErrors (FR-007)", () => {
  it("has no errors without an error", () => {
    expect(formErrors(null, fieldsOfForm)).toEqual({ fields: {}, callout: undefined });
  });

  it("places VALIDATION messages beside their fields, reading a JSON pointer as a name", () => {
    const error = new ApiError(
      422,
      errorEnvelope("VALIDATION", "Invalid.", {
        fields: [
          { field: "email", message: "Bad email." },
          { field: "/password", message: "Too short." },
        ],
      }),
    );
    expect(formErrors(error, fieldsOfForm)).toEqual({
      fields: { email: "Bad email.", password: "Too short." },
      callout: undefined,
    });
  });

  it("puts a message for a field the form does not have in the callout", () => {
    const error = new ApiError(
      422,
      errorEnvelope("VALIDATION", "Invalid.", { fields: [{ field: "other", message: "Nope." }] }),
    );
    expect(formErrors(error, fieldsOfForm)).toEqual({ fields: {}, callout: "Nope." });
  });

  it("shows any other error as a callout", () => {
    const error = new ApiError(409, errorEnvelope("CONFLICT", "Already used."));
    expect(formErrors(error, fieldsOfForm)).toEqual({ fields: {}, callout: "Already used." });
    expect(formErrors(new Error("boom"), fieldsOfForm).callout).toBe("boom");
  });
});
