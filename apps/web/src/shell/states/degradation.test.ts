import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { DEPENDENCIES } from "../../api/dependencies";
import { BUDGET_ROW, DEPENDENCY_ROWS, SCREEN_WORDING } from "./degradation";

const architectureRoot = resolve(process.cwd(), "../../docs/architecture");

function tableRows(file: string, headerStart: string): string[][] {
  const lines = readFileSync(resolve(architectureRoot, file), "utf8").split("\n");
  const start = lines.findIndex((line) => line.startsWith(headerStart));
  const rows: string[][] = [];
  for (const line of lines.slice(start + 2)) {
    if (!line.startsWith("|")) {
      break;
    }
    rows.push(
      line
        .split("|")
        .slice(1, -1)
        .map((cell) => cell.trim()),
    );
  }
  return rows;
}

/** The Dependencies table: code, dependency value, when raised, and the Degradation row. */
const dependenciesTable = tableRows("interfaces.md", "| Code | `details.dependency` |");
/** The Degradation table: row name, what happens, what still works, and the Screen wording. */
const degradationTable = tableRows("overview.md", "| Dependency down |");

function unquote(cell: string | undefined): string {
  return (cell ?? "").replaceAll("`", "");
}

/** Parses the fixed shape of a Screen wording cell. */
function parseWording(cell: string) {
  const match = /^\*\*(.+?)\*\* (.+)$/.exec(cell);
  const headline = match?.[1] ?? "";
  const rest = match?.[2] ?? "";
  return rest.startsWith("Still works: ")
    ? { headline, stillWorks: rest.slice("Still works: ".length).split(" · ") }
    : { headline, closing: rest };
}

describe("degradation.ts against its owning tables (DC-17, R-6)", () => {
  it("DEPENDENCIES and DEPENDENCY_ROWS are the Dependencies table of Conventions", () => {
    const upstream = dependenciesTable.filter((row) => row[0] === "`UPSTREAM_UNAVAILABLE`");
    expect(upstream).toHaveLength(5);
    expect([...DEPENDENCIES]).toEqual(upstream.map((row) => unquote(row[1])));
    expect(DEPENDENCY_ROWS).toEqual(
      Object.fromEntries(upstream.map((row) => [unquote(row[1]), row[3]])),
    );
    const budget = dependenciesTable.find((row) => row[0] === "`BUDGET_EXHAUSTED`");
    expect(BUDGET_ROW).toBe(budget?.[3]);
  });

  it("every Degradation row the Dependencies table names exists", () => {
    const names = degradationTable.map((row) => row[0]);
    for (const row of dependenciesTable) {
      expect(names).toContain(row[3]);
    }
  });

  it("SCREEN_WORDING is the Screen wording cell of each row the Dependencies table names", () => {
    const named = dependenciesTable.map((row) => row[3]);
    const expected: Record<string, ReturnType<typeof parseWording>> = {};
    for (const row of degradationTable) {
      if (named.includes(row[0])) {
        expected[row[0] ?? ""] = parseWording(row[3] ?? "");
      }
    }
    expect(Object.keys(expected)).toHaveLength(6);
    expect(SCREEN_WORDING).toEqual(expected);
  });
});
