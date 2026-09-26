import { describe, expect, it } from "vitest";

import { excludedScore, rankedScore } from "../../../api/pending/prospectsAndEvidence.fixtures";
import { inShort } from "./inShort";

const NOW = new Date("2026-09-25T06:00:00Z");
const example1 = rankedScore;
const example2 = excludedScore;

describe("inShort", () => {
  it("FR-069: Example 1 names the criteria, the two top positive signals and the negative one", () => {
    const text = inShort(example1, NOW);

    expect(text).toContain("Matches: Sector, Region, Complexity.");
    expect(text).toContain("Unknown: Size.");
    expect(text).toContain(
      "Strongest signals: Cost programme (Strong, 1 month ago) and Automation hiring (Clear, 4 weeks ago).",
    );
    expect(text).toContain("Holding back: In-house automation capability (Strong, 3 months ago).");
    expect(text).not.toContain("AI and automation projects");
  });

  it("FR-069, RULE-10: Example 2 states the disqualifier's label as the reason", () => {
    const text = inShort(example2, NOW);

    expect(text).toContain("Does not match: Region.");
    expect(text).toContain("Excluded by the rule Outside DACH.");
  });

  it("FR-069: below fit and customer standings state their reasons", () => {
    const belowFit = {
      ...example1,
      breakdown: { ...example1.breakdown, standing: "BELOW_FIT" as const },
    };
    expect(inShort(belowFit, NOW)).toContain("Below the minimum fit.");

    const customer = {
      ...example1,
      breakdown: { ...example1.breakdown, standing: "CUSTOMER" as const },
    };
    expect(inShort(customer, NOW)).toContain("Marked as a customer.");
  });
});
