import { describe, expect, it } from "vitest";

import { willIncrementRevision, type QuestionFormShape } from "./questionForm";

function shape(overrides: Partial<QuestionFormShape> = {}): QuestionFormShape {
  return {
    text: "Does the company announce a cost-reduction programme?",
    answer_type: "YES_NO",
    options: null,
    source_types: ["NEWS"],
    ...overrides,
  };
}

describe("willIncrementRevision (FR-024)", () => {
  it("is true when the text changes", () => {
    expect(willIncrementRevision(shape(), shape({ text: "Different text?" }))).toBe(true);
  });

  it("is true when the answer type changes", () => {
    expect(willIncrementRevision(shape(), shape({ answer_type: "SCALE" }))).toBe(true);
  });

  it("is true when the options change", () => {
    const saved = shape({
      answer_type: "CHOICE",
      options: [{ key: "YES", label: "Yes", strength: "STRONG" }],
    });
    const edited = shape({
      answer_type: "CHOICE",
      options: [{ key: "YES", label: "Yes", strength: "WEAK" }],
    });
    expect(willIncrementRevision(saved, edited)).toBe(true);
  });

  it("is true when the source types change", () => {
    expect(
      willIncrementRevision(shape(), shape({ source_types: ["NEWS", "JOB_POSTING"] })),
    ).toBe(true);
  });

  it("is false when nothing in the shape changed", () => {
    expect(willIncrementRevision(shape(), shape())).toBe(false);
  });
});
