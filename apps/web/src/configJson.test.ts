import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const script = resolve(process.cwd(), "config-json.sh");

function run(env: Record<string, string>) {
  return spawnSync("sh", [script], {
    env: { PATH: process.env["PATH"] ?? "", ...env },
    encoding: "utf8",
  });
}

describe("config-json.sh (frontend Design)", () => {
  it("prints exactly the Runtime keys the client reads, with their values", () => {
    const result = run({ CONFIDENCE_HIGH_MIN: "0.85", CONFIDENCE_MEDIUM_MIN: "0.65" });
    expect(result.status).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual({
      CONFIDENCE_HIGH_MIN: "0.85",
      CONFIDENCE_MEDIUM_MIN: "0.65",
    });
  });

  it.each(["CONFIDENCE_HIGH_MIN", "CONFIDENCE_MEDIUM_MIN"])(
    "exits non-zero naming %s when it is missing, with no default",
    (missing) => {
      const env = { CONFIDENCE_HIGH_MIN: "0.85", CONFIDENCE_MEDIUM_MIN: "0.65" };
      const partial = Object.fromEntries(Object.entries(env).filter(([key]) => key !== missing));
      const result = run(partial);
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain(missing);
      expect(result.stdout).toBe("");
    },
  );
});
