import { describe, expect, it } from "vitest";

import { toUpperSnakeInput } from "./upperSnake";

describe("toUpperSnakeInput (FR-019, FR-155)", () => {
  it("upper-cases lower-case letters", () => {
    expect(toUpperSnakeInput("cost program")).toBe("COST_PROGRAM");
  });

  it("turns spaces into underscores", () => {
    expect(toUpperSnakeInput("A B C")).toBe("A_B_C");
  });

  it("keeps digits and underscores", () => {
    expect(toUpperSnakeInput("PLAN_2024")).toBe("PLAN_2024");
  });

  it("drops punctuation and other characters", () => {
    expect(toUpperSnakeInput("cost-reduction (2024)!")).toBe("COSTREDUCTION_2024");
  });

  it("passes an already-valid value through unchanged", () => {
    expect(toUpperSnakeInput("ALREADY_VALID")).toBe("ALREADY_VALID");
  });
});
