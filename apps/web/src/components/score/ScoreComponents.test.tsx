import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import type { components } from "../../api/schema.gen";
import {
  BandChip,
  BandLegend,
  CriterionRow,
  EvidenceExcerpt,
  QuoteBlock,
  ScoreNumbers,
  SignalRow,
  StandingChip,
  StrengthChip,
} from ".";

const question: components["schemas"]["ScoreViewQuestionBreakdown"] = {
  decay: 1,
  finding_id: "00000000-0000-0000-0000-000000000001",
  points: 53,
  polarity: "POSITIVE",
  question_key: "AUTOMATION",
  question_text: "AI and automation projects",
  strength: "STRONG",
  value: 1,
  weight: "HIGH",
  weight_value: 1,
};
const criterion: components["schemas"]["FitCriterionBreakdown"] = {
  attribute: null,
  credit: 0.5,
  key: "SIZE",
  kind: "EMPLOYEE_RANGE",
  match: "UNKNOWN",
  points: 12.5,
  weight: "MEDIUM",
  weight_value: 0.5,
};
const finding: components["schemas"]["FindingView"] = {
  account_id: "a",
  confidence: 0.9,
  decided_by: "LLM",
  document: {
    id: "d",
    language: "de",
    plugin_code: "WEBSITE",
    published_at: null,
    source_type: "COMPANY_PUBLICATION",
    title: "News",
    url: "https://group.example/news",
  },
  feedback: null,
  id: "f",
  observed_at: "2026-09-05T00:00:00Z",
  option: null,
  points: 53,
  question: { id: "q", key: "AUTOMATION", polarity: "POSITIVE", text: "Projects?" },
  question_revision: 1,
  quote: "Automatisierung",
  quote_en: "Automation",
  rationale: null,
  service_id: "s",
  status: "ACTIVE",
  strength: "STRONG",
};

it("FR-111 through FR-117 render the contract's score anatomy", async () => {
  const settings: components["schemas"]["ScoringSettingsDocument"] = {
    default_half_life_days: {},
    disqualifiers: [],
    fit_weight: 0.5,
    hot_threshold: 70,
    icp_criteria: [],
    intent_saturation: 100,
    intent_weight: 0.5,
    min_decay: 0.1,
    min_fit: 40,
    negative_factor: 1,
    questions: [],
    strength_values: {},
    unknown_match: 0.5,
    warm_threshold: 50,
    weight_values: {},
  };
  const { container } = render(
    <>
      <BandChip band="HOT" />
      <BandChip band="WARM" />
      <BandChip band="COLD" />
      <StandingChip standing="CUSTOMER" />
      <ScoreNumbers priority={78} fit={88} intent={72} />
      <CriterionRow criterion={criterion} />
      <SignalRow question={question} />
      <StrengthChip strength="MEDIUM" decidedBy="LLM" />
      <QuoteBlock finding={finding} now={new Date("2026-09-26T00:00:00Z")} />
      <EvidenceExcerpt
        evidence={{
          document: finding.document,
          excerpt: "Before quoted after",
          finding_id: "f",
          purged: false,
          quote_start: 7,
          quote_end: 13,
          section: null,
        }}
      />
      <BandLegend settings={settings} />
    </>,
  );
  for (const label of [
    "Hot",
    "Warm",
    "Cold",
    "Customer",
    "Priority",
    "Add the employee count to sharpen this score",
    "AI and automation projects",
    "Clear",
    "Detailed check",
    "quoted",
  ])
    expect(screen.getByText(label)).toBeVisible();
  expect(screen.getByText("Fit", { exact: false })).toBeVisible();
  expect(screen.getByText("Intent", { exact: false })).toBeVisible();
  expect(screen.getByText("English: Automation", { exact: false })).toBeVisible();
  expect(screen.getByText("Warm from 50", { exact: false })).toHaveTextContent("Hot from 70");
  expect(
    (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
  ).toEqual([]);
});

it.each([
  ["POSITIVE", 5, "Positive signal", "+5"],
  ["NEGATIVE", -5, "Negative signal", "-5"],
] as const)("FR-113 renders %s polarity and signed points", (polarity, points, label, signed) => {
  render(<SignalRow question={{ ...question, polarity, points }} />);
  expect(screen.getByLabelText(label)).toBeVisible();
  expect(screen.getByText(signed)).toBeVisible();
});

it.each([
  ["MATCH", "match", "Germany"],
  ["MISMATCH", "mismatch", "Germany"],
  ["UNKNOWN", "unknown", "Add the country to sharpen this score"],
] as const)("FR-114 renders the %s mark", (match, label, text) => {
  render(
    <CriterionRow
      criterion={{
        ...criterion,
        attribute: match === "UNKNOWN" ? null : "Germany",
        kind: "GEOGRAPHY",
        match,
      }}
    />,
  );
  expect(screen.getByLabelText(label)).toBeVisible();
  expect(screen.getByText(text)).toBeVisible();
});

it.each([
  ["NONE", "None"],
  ["WEAK", "Weak"],
  ["MEDIUM", "Clear"],
  ["STRONG", "Strong"],
] as const)("FR-115 renders %s strength", (strength, label) => {
  render(<StrengthChip strength={strength} decidedBy="CLASSIFIER" />);
  expect(screen.getByText(label)).toBeVisible();
});

it.each([
  ["CLASSIFIER", "Quick check"],
  ["LLM", "Detailed check"],
] as const)("FR-115 renders %s decision method", (decidedBy, label) => {
  render(<StrengthChip strength="STRONG" decidedBy={decidedBy} />);
  expect(screen.getByText(label)).toBeVisible();
});
