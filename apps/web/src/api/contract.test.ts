import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = process.cwd();

function freshGeneration(input: string): string {
  const out = join(mkdtempSync(join(tmpdir(), "leadradar-gen-")), "schema.gen.ts");
  execFileSync("npx", ["openapi-typescript", input, "-o", out], { cwd: webRoot, stdio: "pipe" });
  return readFileSync(out, "utf8");
}

describe("contract files", () => {
  it("the committed schema.gen.ts equals a fresh generation from apps/api/openapi.json", () => {
    expect(readFileSync(resolve(webRoot, "src/api/schema.gen.ts"), "utf8")).toBe(
      freshGeneration("../api/openapi.json"),
    );
  });
});
