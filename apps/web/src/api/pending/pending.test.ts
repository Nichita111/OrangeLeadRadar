import { describe, expect, it } from "vitest";

import apiDocument from "../../../../api/openapi.json";
import fragment from "./openapi.json";

describe("pending contracts", () => {
  it("API-39 to API-45: the api has not declared a path of the pending fragment yet", () => {
    const declared = Object.keys(apiDocument.paths);
    const pendingPaths = Object.keys(fragment.paths);

    expect(pendingPaths.filter((path) => declared.includes(path))).toEqual([]);
  });
});
