import { describe, expect, it } from "vitest";

import { activationRescore, type Run } from "./runs";

function run(overrides: Partial<Run>): Run {
  return {
    id: crypto.randomUUID(),
    kind: "RESCORE",
    trigger: "FEEDBACK",
    status: "QUEUED",
    stage: null,
    progress: {},
    errors: [],
    account: null,
    service: null,
    question: null,
    requested_by_name: null,
    created_at: "2026-09-27T00:00:00Z",
    started_at: null,
    finished_at: null,
    ai_cost_eur: 0,
    ...overrides,
  };
}

describe("activationRescore (G1 b, FR-036)", () => {
  it("picks the first SCORING_ACTIVATION run above account rescores of the same service", () => {
    const activation = run({ id: "activation", trigger: "SCORING_ACTIVATION" });
    const runs = [run({ id: "feedback", trigger: "FEEDBACK" }), activation];
    expect(activationRescore(runs)).toBe(activation);
  });

  it("is undefined when there is no SCORING_ACTIVATION run", () => {
    const runs = [run({ trigger: "FEEDBACK" }), run({ trigger: "OVERRIDE" })];
    expect(activationRescore(runs)).toBeUndefined();
  });

  it("is undefined for an empty list", () => {
    expect(activationRescore([])).toBeUndefined();
  });
});
