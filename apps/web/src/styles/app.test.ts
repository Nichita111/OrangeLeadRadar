import fs from "node:fs";
import { expect, it } from "vitest";

it("FR-106 applies the body typography tokens at the root", () => {
  const css = fs.readFileSync("src/styles/app.css", "utf8");

  expect(css).toMatch(/body\s*{[^}]*font-size:\s*var\(--text-body\)/s);
  expect(css).toMatch(/body\s*{[^}]*line-height:\s*var\(--text-body--line-height\)/s);
});
