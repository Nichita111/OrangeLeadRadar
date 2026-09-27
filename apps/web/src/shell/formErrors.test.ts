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

  it("places a pointer error on the longest registered prefix (FR-034)", () => {
    const formFields = ["/icp_criteria/2", "/icp_criteria/2/values", "/questions/1/weight"];
    const error = new ApiError(
      422,
      errorEnvelope("VALIDATION", "Invalid.", {
        fields: [
          { field: "/icp_criteria/2/values", message: "Values are invalid." },
          { field: "/questions/1/weight", message: "Weight is invalid." },
        ],
      }),
    );
    expect(formErrors(error, formFields)).toEqual({
      fields: {
        "/icp_criteria/2/values": "Values are invalid.",
        "/questions/1/weight": "Weight is invalid.",
      },
      callout: undefined,
    });
  });

  it("puts a pointer with no registered field or prefix in the callout", () => {
    const formFields = ["/icp_criteria/2"];
    const error = new ApiError(
      422,
      errorEnvelope("VALIDATION", "Invalid.", {
        fields: [{ field: "/disqualifiers/0/question_key", message: "Unknown question." }],
      }),
    );
    expect(formErrors(error, formFields)).toEqual({
      fields: {},
      callout: "Unknown question.",
    });
  });
});
