// `FR-008`, `FR-009`, `FR-011`: confidence thresholds; every band, standing, strength and
// `decided_by` value maps to its screen label; an unlisted enum is title-cased.
import { describe, expect, it } from "vitest";

import {
  bandLabel,
  confidenceWord,
  decidedByLabel,
  standingLabel,
  strengthLabel,
  termLabel,
  titleCaseFallback,
} from "./labels";

describe("confidenceWord", () => {
  it("gives High at CONFIDENCE_HIGH_MIN and above", () => {
    expect(confidenceWord(0.85, 0.85, 0.65)).toBe("High");
  });
  it("gives Medium just below CONFIDENCE_HIGH_MIN", () => {
    expect(confidenceWord(0.849, 0.85, 0.65)).toBe("Medium");
  });
  it("gives Medium at CONFIDENCE_MEDIUM_MIN", () => {
    expect(confidenceWord(0.65, 0.85, 0.65)).toBe("Medium");
  });
  it("gives Low just below CONFIDENCE_MEDIUM_MIN", () => {
    expect(confidenceWord(0.649, 0.85, 0.65)).toBe("Low");
  });
});

describe("screen-label maps", () => {
  it("maps every band value", () => {
    expect(bandLabel("HOT")).toBe("Hot");
    expect(bandLabel("WARM")).toBe("Warm");
    expect(bandLabel("COLD")).toBe("Cold");
  });

  it("maps every standing value", () => {
    expect(standingLabel("RANKED")).toBe("Ranked");
    expect(standingLabel("BELOW_FIT")).toBe("Below fit");
    expect(standingLabel("DISQUALIFIED")).toBe("Excluded");
    expect(standingLabel("CUSTOMER")).toBe("Customer");
  });

  it("maps every strength value", () => {
    expect(strengthLabel("WEAK")).toBe("Weak");
    expect(strengthLabel("MEDIUM")).toBe("Clear");
    expect(strengthLabel("STRONG")).toBe("Strong");
  });

  it("maps every decided_by value", () => {
    expect(decidedByLabel("CLASSIFIER")).toBe("Quick check");
    expect(decidedByLabel("LLM")).toBe("Detailed check");
  });

  it("title-cases an unlisted enum value", () => {
    expect(titleCaseFallback("NOT_CONFIGURED")).toBe("Not configured");
  });

  it("uses the specified term labels", () => {
    expect(termLabel("finding")).toBe("Signal");
    expect(termLabel("disqualifier_override")).toBe("Exception");
    expect(termLabel("discovery_candidate")).toBe("Suggested account");
    expect(termLabel("evaluation_run")).toBe("Quality check");
    expect(termLabel("scoring_settings")).toBe("Scoring");
  });
});
