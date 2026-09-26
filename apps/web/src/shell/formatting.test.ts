import { describe, expect, it } from "vitest";

import { RUNTIME_CONFIG_DEFAULTS } from "../api/config";
import { countryName } from "./countries";
import { confidenceWord } from "./formatting";

describe("formatting", () => {
  it("FR-009: a confidence is High at its threshold, Medium at its threshold, Low below", () => {
    const { CONFIDENCE_HIGH_MIN: high, CONFIDENCE_MEDIUM_MIN: medium } = RUNTIME_CONFIG_DEFAULTS;
    expect(confidenceWord(high, RUNTIME_CONFIG_DEFAULTS)).toBe("High");
    expect(confidenceWord(high - 0.001, RUNTIME_CONFIG_DEFAULTS)).toBe("Medium");
    expect(confidenceWord(medium, RUNTIME_CONFIG_DEFAULTS)).toBe("Medium");
    expect(confidenceWord(medium - 0.001, RUNTIME_CONFIG_DEFAULTS)).toBe("Low");
  });

  it("FR-011: a country code is shown with its English name", () => {
    expect(countryName("DE")).toBe("Germany");
  });
});
