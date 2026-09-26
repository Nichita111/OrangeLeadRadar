// [Runtime](/architecture/services/frontend.md#runtime); [coding Errors](/guidelines/coding.md#errors):
// no fallback, so a missing or ill-typed key throws, naming the key.
import { describe, expect, it } from "vitest";

import { parseClientConfig } from "./config";

const VALID_CONFIG = {
  RUN_POLL_INTERVAL_MS: 2000,
  ALERT_POLL_INTERVAL_MS: 60000,
  CONFIDENCE_HIGH_MIN: 0.85,
  CONFIDENCE_MEDIUM_MIN: 0.65,
  MOCK_API: false,
};

describe("parseClientConfig", () => {
  it("parses the config the default script prints", () => {
    expect(parseClientConfig(VALID_CONFIG)).toEqual(VALID_CONFIG);
  });

  it("throws naming a missing key", () => {
    const withoutMockApi: Record<string, unknown> = { ...VALID_CONFIG };
    delete withoutMockApi.MOCK_API;
    expect(() => parseClientConfig(withoutMockApi)).toThrow("MOCK_API");
  });

  it("throws naming a non-numeric interval", () => {
    expect(() => parseClientConfig({ ...VALID_CONFIG, RUN_POLL_INTERVAL_MS: "2000" })).toThrow(
      "RUN_POLL_INTERVAL_MS",
    );
  });
});
