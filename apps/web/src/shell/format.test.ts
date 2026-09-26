import { describe, expect, it } from "vitest";

import { countryName, enumLabel, formatAbsolute, formatRelative } from "./format";

const now = new Date("2026-09-26T12:00:00Z");
const ago = (seconds: number): Date => new Date(now.getTime() - seconds * 1000);
const HOUR = 3600;
const DAY = 24 * HOUR;

describe("formatRelative (FR-010, DC-14)", () => {
  it.each([
    ["30 s ago", ago(30)],
    ["59 min 59 s ago", ago(HOUR - 1)],
    ["20 s in the future (clock skew)", ago(-20)],
  ])("%s reads just now", (_name, at) => {
    expect(formatRelative(at, now)).toBe("just now");
  });

  it.each([
    [HOUR, "1 hour ago"],
    [2 * HOUR, "2 hours ago"],
    [23 * HOUR + 59 * 60, "23 hours ago"],
    [DAY, "yesterday"],
    [3 * DAY, "3 days ago"],
    [7 * DAY, "1 week ago"],
    [21 * DAY, "3 weeks ago"],
    [60 * DAY, "2 months ago"],
    [400 * DAY, "1 year ago"],
    [800 * DAY, "2 years ago"],
  ])("%d s ago reads %s", (seconds, text) => {
    expect(formatRelative(ago(seconds), now)).toBe(text);
  });

  it("never reads today", () => {
    expect(formatRelative(ago(23 * HOUR + 59 * 60), now)).not.toMatch(/today/);
  });

  it("accepts an ISO-8601 string", () => {
    expect(formatRelative("2026-09-26T10:00:00Z", now)).toBe("2 hours ago");
  });
});

describe("formatAbsolute (FR-010)", () => {
  it("shows the date and time in the given time zone", () => {
    expect(formatAbsolute("2026-09-26T10:00:00Z", "Europe/Berlin")).toContain("12:00");
  });
});

describe("countryName and enumLabel (FR-011)", () => {
  it("names a country in English", () => {
    expect(countryName("DE")).toBe("Germany");
  });

  it.each([
    ["SALES", "Sales"],
    ["ADMIN", "Admin"],
    ["ACTIVE", "Active"],
    ["DISABLED", "Disabled"],
    ["JOB_POSTING", "Job posting"],
    ["HOT", "Hot"],
    ["DISQUALIFIED", "Excluded"],
    ["CLASSIFIER", "Quick check"],
    ["LLM", "Detailed check"],
  ])("%s reads %s", (value, label) => {
    expect(enumLabel(value)).toBe(label);
  });
});
