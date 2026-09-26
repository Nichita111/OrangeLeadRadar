// `FR-010`, `FR-011`: a relative age for an injected `now`, the absolute tooltip in a given time
// zone, ISO-8601 for exports, and `DE` gives Germany.
import { describe, expect, it } from "vitest";

import { absoluteTooltip, countryName, isoExport, relativeAge } from "./formatting";

describe("relativeAge", () => {
  it("shows a relative age for an injected now", () => {
    const now = new Date("2026-09-26T12:00:00Z");
    const threeDaysAgo = new Date("2026-09-23T12:00:00Z");
    expect(relativeAge(threeDaysAgo, now)).toBe("3 days ago");
  });
});

describe("absoluteTooltip", () => {
  it("shows the absolute date and time in the given time zone", () => {
    const date = new Date("2026-09-26T12:00:00Z");
    expect(absoluteTooltip(date, "Europe/Berlin")).toContain("2026");
  });
});

describe("isoExport", () => {
  it("formats as ISO-8601", () => {
    const date = new Date("2026-09-26T12:00:00Z");
    expect(isoExport(date)).toBe("2026-09-26T12:00:00.000Z");
  });
});

describe("countryName", () => {
  it("gives Germany for DE", () => {
    expect(countryName("DE")).toBe("Germany");
  });
});
