import { describe, expect, it } from "vitest";

import { safeReturnPath } from "./returnPath";

describe("safeReturnPath (FR-093, DC-4)", () => {
  it.each(["/users", "/accounts/x?tab=y"])("keeps %s", (path) => {
    expect(safeReturnPath(path)).toBe(path);
  });

  it.each(["//evil.example", "https://evil.example", "javascript:alert(1)", "", null, "/\\evil"])(
    "rejects %j",
    (path) => {
      expect(safeReturnPath(path)).toBe("/prospects");
    },
  );
});
