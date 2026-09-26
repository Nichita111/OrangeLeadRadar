import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ cwd: process.cwd() });

describe("PLACEHOLDER tags", () => {
  it("rejects one outside mocks and accepts one inside mocks", async () => {
    const source = `// ${["PLACE", "HOLDER"].join("")}(invented): replaced later\nexport {};`;
    const [shell] = await eslint.lintText(source, { filePath: "src/placeholders.test.ts" });
    const [mock] = await eslint.lintText(source, { filePath: "src/mocks/session.ts" });
    expect(shell?.messages.some((message) => message.ruleId === "no-warning-comments")).toBe(true);
    expect(mock?.messages).toEqual([]);
  });
});
