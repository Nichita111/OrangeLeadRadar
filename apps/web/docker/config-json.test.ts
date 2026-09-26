// [frontend Design](/architecture/services/frontend.md#design) (`/config.json`): the script
// prints valid JSON with the defaults of
// [Runtime](/architecture/services/frontend.md#runtime), and an environment value overrides
// each one.
import { execFileSync } from "node:child_process";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SCRIPT_PATH = path.resolve(import.meta.dirname, "config-json.sh");

function run(env: Record<string, string> = {}): unknown {
  const output = execFileSync("sh", [SCRIPT_PATH], { env: { ...process.env, ...env } });
  return JSON.parse(output.toString());
}

describe("config-json.sh", () => {
  it("prints the Runtime defaults", () => {
    expect(run()).toEqual({
      RUN_POLL_INTERVAL_MS: 2000,
      ALERT_POLL_INTERVAL_MS: 60000,
      CONFIDENCE_HIGH_MIN: 0.85,
      CONFIDENCE_MEDIUM_MIN: 0.65,
      MOCK_API: false,
    });
  });

  it("lets an environment value override each default", () => {
    const config = run({
      RUN_POLL_INTERVAL_MS: "5000",
      ALERT_POLL_INTERVAL_MS: "30000",
      CONFIDENCE_HIGH_MIN: "0.9",
      CONFIDENCE_MEDIUM_MIN: "0.7",
      MOCK_API: "true",
    });

    expect(config).toEqual({
      RUN_POLL_INTERVAL_MS: 5000,
      ALERT_POLL_INTERVAL_MS: 30000,
      CONFIDENCE_HIGH_MIN: 0.9,
      CONFIDENCE_MEDIUM_MIN: 0.7,
      MOCK_API: true,
    });
  });
});
