import { describe, expect, it } from "vitest";

import { confidenceLabel } from "./confidence";

const config = { CONFIDENCE_HIGH_MIN: 0.85, CONFIDENCE_MEDIUM_MIN: 0.65 };

describe("confidenceLabel (FR-009)", () => {
  it.each([
    [0.85, "High"],
    [0.8499, "Medium"],
    [0.65, "Medium"],
    [0.6499, "Low"],
  ])("%s is %s", (value, word) => {
    expect(confidenceLabel(value, config)).toBe(word);
  });

  it("reads its thresholds from the injected config", () => {
    expect(confidenceLabel(0.7, { CONFIDENCE_HIGH_MIN: 0.6, CONFIDENCE_MEDIUM_MIN: 0.3 })).toBe(
      "High",
    );
  });
});
