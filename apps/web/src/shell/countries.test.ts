import { describe, expect, it } from "vitest";

import { COUNTRY_CODES } from "./countries";
import { countryName } from "./format";

describe("COUNTRY_CODES (FR-155, FR-011)", () => {
  it("has 249 entries, each two upper-case letters, with no duplicates", () => {
    expect(COUNTRY_CODES).toHaveLength(249);
    for (const code of COUNTRY_CODES) {
      expect(code).toMatch(/^[A-Z]{2}$/);
    }
    expect(new Set(COUNTRY_CODES).size).toBe(COUNTRY_CODES.length);
  });

  it("has a countryName different from its code for every entry", () => {
    for (const code of COUNTRY_CODES) {
      expect(countryName(code)).not.toBe(code);
    }
  });
});
