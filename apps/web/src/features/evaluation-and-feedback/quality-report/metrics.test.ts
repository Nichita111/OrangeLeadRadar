import { describe, expect, it } from "vitest";

import { parseMetrics } from "./metrics";

describe("parseMetrics", () => {
  it("parses every key of the metrics object", () => {
    const parsed = parseMetrics({
      items: 10,
      tp: 4,
      fp: 1,
      tn: 3,
      fn: 2,
      precision: 0.8,
      recall: null,
      strength_agreement: 0.5,
      escalation_rate: 0.2,
      classifier_only: { precision: 0.7, recall: null },
      per_question: {
        "q-1": {
          key: "COST_PROGRAM",
          service_id: "svc-1",
          items: 5,
          precision: 0.9,
          recall: 0.8,
        },
      },
      per_source_type: {
        NEWS: { items: 5, precision: 0.9, recall: 0.8 },
      },
      missed_evidence: { items: 2, positive_rate: null },
      calibration: [{ count: 0, mean_p: null, positive_rate: null }],
      errors: [
        {
          item_id: "item-1",
          expected: "STRONG",
          predicted: "NONE",
          p_positive: 0.2,
          escalated: false,
          question_key: "COST_PROGRAM",
          passage_text: "A passage.",
          document: { title: "A title", url: "https://example.com" },
        },
      ],
      lead_verdicts: { HOT: { RELEVANT: 2, NOT_RELEVANT: 1 } },
    });

    expect(parsed.items).toBe(10);
    expect(parsed.precision).toBe(0.8);
    expect(parsed.recall).toBeNull();
    expect(parsed.per_question["q-1"]).toEqual({
      key: "COST_PROGRAM",
      service_id: "svc-1",
      items: 5,
      precision: 0.9,
      recall: 0.8,
    });
    expect(parsed.errors[0]?.document).toEqual({ title: "A title", url: "https://example.com" });
    expect(parsed.lead_verdicts["HOT"]).toEqual({ RELEVANT: 2, NOT_RELEVANT: 1 });
  });

  it("defaults missing or malformed fields rather than throwing", () => {
    const parsed = parseMetrics({});
    expect(parsed.items).toBe(0);
    expect(parsed.precision).toBeNull();
    expect(parsed.per_question).toEqual({});
    expect(parsed.calibration).toEqual([]);
    expect(parsed.errors).toEqual([]);
  });
});
