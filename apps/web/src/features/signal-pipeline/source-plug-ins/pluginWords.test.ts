import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { WHAT_IT_READS } from "./pluginWords";

const featuresRoot = resolve(process.cwd(), "../../docs/features");

/** The "What each plug-in reads" table of the Source plug-ins screen section (D3). */
function whatItReadsTable(): Record<string, string> {
  const lines = readFileSync(resolve(featuresRoot, "signal-pipeline.md"), "utf8").split("\n");
  const start = lines.findIndex((line) => line.startsWith("| Plug-in | What it reads |"));
  const table: Record<string, string> = {};
  for (const line of lines.slice(start + 2)) {
    if (!line.startsWith("|")) {
      break;
    }
    const [, code, reads] = line.split("|").map((cell) => cell.trim());
    table[(code ?? "").replaceAll("`", "")] = reads ?? "";
  }
  return table;
}

describe("WHAT_IT_READS against its owning table (D3, FR-143)", () => {
  it("equals the Source plug-ins table, one entry per SourcePluginCode", () => {
    const table = whatItReadsTable();
    expect(Object.keys(table)).toHaveLength(7);
    expect(WHAT_IT_READS).toEqual(table);
  });
});
