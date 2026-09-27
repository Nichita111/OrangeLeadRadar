import { describe, expect, it } from "vitest";

import type { Schemas } from "../../../api/contract";
import {
  addMarketCountries,
  draftFormFields,
  fitShareChoices,
  halfLifePlaceholder,
  retiredIndustryCodes,
  settingsChanged,
} from "./scoringDraft";

function settings(overrides: Partial<Schemas["ScoringSettings"]> = {}): Schemas["ScoringSettings"] {
  return {
    fit_weight: 0.4,
    intent_weight: 0.6,
    min_fit: 40,
    hot_threshold: 70,
    warm_threshold: 40,
    weight_values: { HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 },
    strength_values: { WEAK: 0.5, MEDIUM: 0.75, STRONG: 1 },
    default_half_life_days: {
      NEWS: 90,
      COMPANY_PUBLICATION: 365,
      JOB_POSTING: 60,
      COMPANY_PROFILE: 365,
    },
    min_decay: 0.05,
    negative_factor: 1,
    intent_saturation: 0.5,
    unknown_match: 0.5,
    icp_criteria: [],
    questions: [],
    disqualifiers: [],
    ...overrides,
  };
}

describe("settingsChanged (FR-028)", () => {
  it("is false for two equal documents", () => {
    expect(settingsChanged(settings(), settings())).toBe(false);
  });

  it("is true when a field differs", () => {
    expect(settingsChanged(settings(), settings({ fit_weight: 0.5 }))).toBe(true);
  });
});

describe("fitShareChoices (FR-151, G3)", () => {
  it("is the four fixed values when the stored share is one of them", () => {
    expect(fitShareChoices(0.4)).toEqual([30, 40, 50, 60]);
  });

  it("adds an off-set stored value, in order", () => {
    expect(fitShareChoices(0.45)).toEqual([30, 40, 45, 50, 60]);
  });

  it("adds nothing for an on-set value even at the edges", () => {
    expect(fitShareChoices(0.3)).toEqual([30, 40, 50, 60]);
    expect(fitShareChoices(0.6)).toEqual([30, 40, 50, 60]);
  });
});

describe("addMarketCountries (FR-030)", () => {
  const market: Schemas["Market"] = {
    code: "DACH",
    name: "DACH",
    country_codes: ["DE", "AT", "CH"],
    status: "ACTIVE",
  };

  it("merges without duplicates, keeping the existing order first", () => {
    expect(addMarketCountries(["AT", "FR"], market)).toEqual(["AT", "FR", "DE", "CH"]);
  });

  it("adds nothing new when every country is already present", () => {
    expect(addMarketCountries(["DE", "AT", "CH"], market)).toEqual(["DE", "AT", "CH"]);
  });
});

describe("retiredIndustryCodes (FR-030)", () => {
  const industries: Schemas["Industry"][] = [
    { code: "SHIPPING", label: "Shipping", status: "ACTIVE", account_count: 1 },
    { code: "TELECOM_MEDIA", label: "Telecom and media", status: "INACTIVE", account_count: 1 },
  ];

  it("finds an INDUSTRY criterion naming a retired industry", () => {
    const criteria: Schemas["ICPCriterion"][] = [
      { key: "IND", kind: "INDUSTRY", weight: "HIGH", values: ["SHIPPING", "TELECOM_MEDIA"] },
    ];
    expect(retiredIndustryCodes(criteria, industries)).toEqual(["TELECOM_MEDIA"]);
  });

  it("is empty when no criterion names a retired industry", () => {
    const criteria: Schemas["ICPCriterion"][] = [
      { key: "IND", kind: "INDUSTRY", weight: "HIGH", values: ["SHIPPING"] },
    ];
    expect(retiredIndustryCodes(criteria, industries)).toEqual([]);
  });

  it("ignores non-INDUSTRY criteria", () => {
    const criteria: Schemas["ICPCriterion"][] = [
      { key: "GEO", kind: "GEOGRAPHY", weight: "HIGH", values: ["TELECOM_MEDIA"] },
    ];
    expect(retiredIndustryCodes(criteria, industries)).toEqual([]);
  });
});

describe("draftFormFields (FR-034)", () => {
  it("registers each list item's own pointer at its position in the document", () => {
    const document = settings({
      icp_criteria: [
        { key: "GEO", kind: "GEOGRAPHY", weight: "HIGH", values: ["DE"] },
        { key: "SIZE", kind: "EMPLOYEE_RANGE", weight: "MEDIUM", min: 10 },
      ],
      questions: [{ question_key: "A_SIGNAL", weight: "MEDIUM", half_life_days: null }],
      disqualifiers: [
        { key: "D1", label: "d", kind: "SIGNAL", question_key: "A_SIGNAL", min_strength: "WEAK" },
      ],
    });
    const fields = draftFormFields(document);
    expect(fields).toContain("/icp_criteria/0/values");
    expect(fields).toContain("/icp_criteria/1/min");
    expect(fields).toContain("/icp_criteria/1/max");
    expect(fields).toContain("/questions/0/weight");
    expect(fields).toContain("/disqualifiers/0/question_key");
    expect(fields).toContain("/disqualifiers/0/min_strength");
  });

  it("registers only the section pointers when every list is empty", () => {
    expect(draftFormFields(settings())).toEqual([
      "/fit_weight",
      "/intent_weight",
      "/min_fit",
      "/warm_threshold",
      "/hot_threshold",
      "/weight_values",
      "/strength_values",
      "/default_half_life_days",
      "/min_decay",
      "/negative_factor",
      "/intent_saturation",
      "/unknown_match",
      "/icp_criteria",
      "/questions",
      "/disqualifiers",
    ]);
  });
});

describe("halfLifePlaceholder (FR-031)", () => {
  const defaults = { NEWS: 90, COMPANY_PUBLICATION: 365, JOB_POSTING: 60, COMPANY_PROFILE: 365 };

  it("is one number for a single source type", () => {
    expect(halfLifePlaceholder(["NEWS"], defaults)).toBe("90");
  });

  it("is one number when every source type shares the same default", () => {
    expect(halfLifePlaceholder(["COMPANY_PUBLICATION", "COMPANY_PROFILE"], defaults)).toBe("365");
  });

  it("lists each distinct default when they differ", () => {
    expect(halfLifePlaceholder(["NEWS", "JOB_POSTING"], defaults)).toBe("90 / 60");
  });
});
