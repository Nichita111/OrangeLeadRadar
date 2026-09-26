import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { ADMIN_ENTRIES, WORK_ENTRIES } from "./navigationEntries";

const frontendPath = resolve(process.cwd(), "../../docs/architecture/services/frontend.md");

function documentedEntries(): { label: string; route: string; icon: string }[] {
  const rows: { label: string; route: string; icon: string }[] = [];
  for (const line of readFileSync(frontendPath, "utf8").split("\n")) {
    const match = /^\| ([^|`]+?) \| `(\/[^`]*)` \| `(\w+)` \|$/.exec(line);
    if (match?.[1] !== undefined && match[2] !== undefined && match[3] !== undefined) {
      rows.push({ label: match[1], route: match[2], icon: match[3] });
    }
  }
  return rows;
}

describe("navigation entries (FR-001, FR-101, DC-13)", () => {
  it("are the Entry, Route and Icon table of frontend Navigation", () => {
    expect([...WORK_ENTRIES, ...ADMIN_ENTRIES]).toEqual(documentedEntries());
  });

  it("FR-001: six Work entries and six Admin entries", () => {
    expect(WORK_ENTRIES.map((entry) => entry.label)).toEqual([
      "Prospects",
      "Alerts",
      "Accounts",
      "Suggested accounts",
      "Runs",
      "Labelling",
    ]);
    expect(ADMIN_ENTRIES.map((entry) => entry.label)).toEqual([
      "Services",
      "Industries and markets",
      "Quality",
      "Source plug-ins",
      "Users",
      "Audit log",
    ]);
  });
});
