import { describe, expect, it } from "vitest";

import type { Schemas } from "../../../api/contract";
import { availability, keyNote } from "./availability";

function plugin(overrides: Partial<Schemas["SourcePlugin"]>): Schemas["SourcePlugin"] {
  return {
    code: "GDELT",
    enabled: true,
    rate_limit_per_minute: 10,
    daily_quota: null,
    needs_key: false,
    key_configured: false,
    available: true,
    requests_today: 0,
    last_success_at: null,
    last_error: null,
    last_error_at: null,
    ...overrides,
  };
}

// FR-143, FR-060: the client never decides availability; it only names which input the rule
// (Plug-in availability) refused, in the order the rule reads it — switch, then key, then quota.
describe("availability (FR-143, FR-060)", () => {
  it("is AVAILABLE when the contract says so", () => {
    expect(availability(plugin({ available: true }))).toEqual({ kind: "AVAILABLE" });
  });

  it("is SWITCHED_OFF when disabled and no key is needed", () => {
    expect(availability(plugin({ available: false, enabled: false, needs_key: false }))).toEqual({
      kind: "SWITCHED_OFF",
    });
  });

  it("is KEY_MISSING when enabled but the needed key is missing", () => {
    expect(
      availability(
        plugin({ available: false, enabled: true, needs_key: true, key_configured: false }),
      ),
    ).toEqual({ kind: "KEY_MISSING" });
  });

  it("is SWITCHED_OFF, not KEY_MISSING, when disabled and the key is also missing", () => {
    expect(
      availability(
        plugin({ available: false, enabled: false, needs_key: true, key_configured: false }),
      ),
    ).toEqual({ kind: "SWITCHED_OFF" });
    expect(keyNote(plugin({ enabled: false, needs_key: true, key_configured: false }))).toBe(true);
  });

  it("is QUOTA_REACHED when enabled, keyed and requests today reached the daily quota", () => {
    expect(
      availability(
        plugin({
          available: false,
          enabled: true,
          needs_key: true,
          key_configured: true,
          requests_today: 100,
          daily_quota: 100,
        }),
      ),
    ).toEqual({ kind: "QUOTA_REACHED" });
  });
});

describe("keyNote (FR-060)", () => {
  it("is false for a plug-in that needs no key", () => {
    expect(keyNote(plugin({ needs_key: false }))).toBe(false);
  });

  it("is false once the key is set", () => {
    expect(keyNote(plugin({ needs_key: true, key_configured: true }))).toBe(false);
  });

  it("is true whatever the switch, when the needed key is missing", () => {
    expect(keyNote(plugin({ needs_key: true, key_configured: false, enabled: true }))).toBe(true);
    expect(keyNote(plugin({ needs_key: true, key_configured: false, enabled: false }))).toBe(true);
  });
});
