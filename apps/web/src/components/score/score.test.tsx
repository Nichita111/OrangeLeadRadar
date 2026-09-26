import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import type { Schemas } from "../../api/contract";
import { ConfigProvider } from "../../configContext";
import { testConfig } from "../../testRender";
import { BandChip, StandingChip } from "./BandChip";
import { CriterionRow } from "./CriterionRow";
import { EvidenceExcerpt } from "./EvidenceExcerpt";
import { Quote } from "./Quote";
import { ScoreNumber } from "./ScoreNumber";
import { SignalRow } from "./SignalRow";
import { StrengthChip } from "./StrengthChip";

describe("ScoreNumber (FR-112)", () => {
  it("shows Priority larger than Fit, in the mono face, with the meaning line", () => {
    render(
      <>
        <ScoreNumber label="Priority" value={78} size="large" />
        <ScoreNumber label="Fit" value={88} meaning="How well it matches" />
      </>,
    );
    const priority = screen.getByText("78");
    const fit = screen.getByText("88");
    expect(priority.className).toMatch(/\bnum\b/);
    expect(priority.className).toMatch(/text-title/);
    expect(fit.className).not.toMatch(/text-title/);
    expect(screen.getByText("How well it matches")).toBeInTheDocument();
    expect(screen.getByText("Priority")).toBeInTheDocument();
  });

  it("draws its bar without a track", () => {
    const { container } = render(<ScoreNumber label="Fit" value={50} meaning="x" />);
    expect(container.querySelectorAll("[data-bar]")).toHaveLength(1);
    expect(container.querySelector("[data-bar-track]")).toBeNull();
  });
});

describe("Quote (FR-116)", () => {
  it("shows the translation only when given, then source domain, label and age", () => {
    const { rerender } = render(
      <Quote
        text="DHL setzt KI-Agenten ein."
        sourceDomain="group.dhl.com"
        sourceLabel="Press release"
        at="2026-09-05T12:00:00Z"
        now={new Date("2026-09-26T12:00:00Z")}
      />,
    );
    expect(screen.getByText("DHL setzt KI-Agenten ein.")).toBeInTheDocument();
    expect(screen.queryByText(/English:/)).not.toBeInTheDocument();
    expect(screen.getByText(/group\.dhl\.com/)).toBeInTheDocument();
    expect(screen.getByText("3 weeks ago")).toBeInTheDocument();

    rerender(
      <Quote
        text="DHL setzt KI-Agenten ein."
        english="DHL uses AI agents."
        sourceDomain="group.dhl.com"
        sourceLabel="Press release"
        at="2026-09-05T12:00:00Z"
        now={new Date("2026-09-26T12:00:00Z")}
      />,
    );
    expect(screen.getByText(/DHL uses AI agents\./)).toBeInTheDocument();
  });
});

const QUESTION: Schemas["ScoreViewQuestionBreakdown"] = {
  decay: 1,
  finding_id: "00000000-0000-0000-0000-000000000001",
  observed_at: "2026-09-05T00:00:00Z",
  points: 53,
  polarity: "POSITIVE",
  question_key: "AUTOMATION",
  question_text: "AI and automation projects",
  strength: "STRONG",
  value: 1,
  weight: "HIGH",
  weight_value: 1,
};
const CRITERION: Schemas["FitCriterionBreakdown"] = {
  attribute: null,
  credit: 0.5,
  key: "SIZE",
  kind: "EMPLOYEE_RANGE",
  match: "UNKNOWN",
  points: 12.5,
  weight: "MEDIUM",
  weight_value: 0.5,
};
const EVIDENCE_DOCUMENT: Schemas["FindingDocument"] = {
  id: "d",
  language: "de",
  plugin_code: "WEBSITE",
  published_at: null,
  source_type: "COMPANY_PUBLICATION",
  title: "News",
  url: "https://group.example/news",
};

describe("FR-111 through FR-117: the score anatomy", () => {
  it("renders a band chip, filled for Hot, soft for Warm, cool for Cold", () => {
    render(
      <>
        <BandChip band="HOT" />
        <BandChip band="WARM" />
        <BandChip band="COLD" />
      </>,
    );
    expect(screen.getByText("Hot").closest("span")).toHaveClass("bg-accent");
    expect(screen.getByText("Warm").closest("span")).toHaveClass("bg-accent-soft");
    expect(screen.getByText("Cold").closest("span")).toHaveClass("bg-cool-soft");
  });

  it("renders a standing other than Ranked as a neutral chip with no band icon", () => {
    const { container } = render(<StandingChip standing="CUSTOMER" />);
    expect(screen.getByText("Customer")).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeNull();
  });

  it.each([
    ["POSITIVE", 5, "Positive signal", "+5"],
    ["NEGATIVE", -5, "Negative signal", "-5"],
  ] as const)(
    "FR-113 renders %s polarity with a filled mark and signed points",
    (polarity, points, label, signed) => {
      render(<SignalRow question={{ ...QUESTION, polarity, points }} />);
      expect(screen.getByLabelText(label)).toBeVisible();
      expect(screen.getByText(signed)).toBeVisible();
    },
  );

  it.each([
    ["MATCH", "match", "Germany"],
    ["MISMATCH", "mismatch", "Germany"],
    ["UNKNOWN", "unknown", "Add the country to sharpen this score"],
  ] as const)(
    "FR-114 renders the %s mark, the criterion icon and the weight level",
    (match, label, text) => {
      render(
        <CriterionRow
          criterion={{
            ...CRITERION,
            attribute: match === "UNKNOWN" ? null : "Germany",
            kind: "GEOGRAPHY",
            match,
          }}
        />,
      );
      expect(screen.getByLabelText(label)).toBeVisible();
      expect(screen.getByText(text)).toBeVisible();
      expect(screen.getByText("Medium")).toBeVisible();
    },
  );

  it("FR-114 names the fact of the table for every criterion kind", () => {
    render(
      <>
        <CriterionRow criterion={{ ...CRITERION, kind: "INDUSTRY", attribute: null }} />
        <CriterionRow criterion={{ ...CRITERION, kind: "REVENUE_RANGE", attribute: null }} />
        <CriterionRow
          criterion={{ ...CRITERION, kind: "OPERATIONAL_COMPLEXITY", attribute: null }}
        />
      </>,
    );
    expect(screen.getByText("Add the industry to sharpen this score")).toBeVisible();
    expect(screen.getByText("Add the revenue to sharpen this score")).toBeVisible();
    expect(screen.getByText("Add the operational complexity to sharpen this score")).toBeVisible();
  });

  it.each([
    ["WEAK", "Weak"],
    ["MEDIUM", "Clear"],
    ["STRONG", "Strong"],
  ] as const)("FR-115 renders %s strength as %s", (strength, label) => {
    render(
      <ConfigProvider config={testConfig}>
        <StrengthChip strength={strength} confidence={0.9} decidedBy="CLASSIFIER" />
      </ConfigProvider>,
    );
    expect(screen.getByText(label)).toBeVisible();
  });

  it.each([
    ["CLASSIFIER", "Quick check"],
    ["LLM", "Detailed check"],
  ] as const)(
    "FR-115 renders the %s decision as %s, and the confidence as a word",
    (decidedBy, label) => {
      render(
        <ConfigProvider config={testConfig}>
          <StrengthChip strength="STRONG" confidence={0.9} decidedBy={decidedBy} />
        </ConfigProvider>,
      );
      expect(screen.getByText(label)).toBeVisible();
      expect(screen.getByText("High")).toBeVisible();
      expect(screen.queryByText(/0\.9/)).not.toBeInTheDocument();
    },
  );

  it("FR-116 marks exactly quote_start to quote_end, and shows plain text when purged", () => {
    const { rerender } = render(
      <EvidenceExcerpt
        evidence={{
          document: EVIDENCE_DOCUMENT,
          excerpt: "Before quoted after",
          finding_id: "f",
          purged: false,
          quote_start: 7,
          quote_end: 13,
          section: null,
        }}
      />,
    );
    expect(screen.getByText("quoted")).toBeVisible();
    expect(screen.getByText("quoted").tagName).toBe("MARK");

    rerender(
      <EvidenceExcerpt
        evidence={{
          document: EVIDENCE_DOCUMENT,
          excerpt: null,
          finding_id: "f",
          purged: true,
          quote_start: null,
          quote_end: null,
          section: null,
        }}
      />,
    );
    expect(screen.queryByRole("mark")).toBeNull();
  });

  it("reports no axe violation", async () => {
    const { container } = render(
      <ConfigProvider config={testConfig}>
        <BandChip band="HOT" />
        <StandingChip standing="CUSTOMER" />
        <SignalRow question={QUESTION} />
        <CriterionRow criterion={CRITERION} />
        <StrengthChip strength="MEDIUM" confidence={0.9} decidedBy="LLM" />
        <EvidenceExcerpt
          evidence={{
            document: EVIDENCE_DOCUMENT,
            excerpt: "Before quoted after",
            finding_id: "f",
            purged: false,
            quote_start: 7,
            quote_end: 13,
            section: null,
          }}
        />
      </ConfigProvider>,
    );
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
