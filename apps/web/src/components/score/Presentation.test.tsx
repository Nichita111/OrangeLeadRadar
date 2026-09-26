import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { axe } from "vitest-axe";

import type { components } from "../../api/schema.gen";
import { absoluteTooltip } from "../../shell/formatting";
import { ConfigProvider, type ClientConfig } from "../../shell/config";
import { QuoteBlock } from "./QuoteBlock";

const config: ClientConfig = {
  RUN_POLL_INTERVAL_MS: 2_000,
  ALERT_POLL_INTERVAL_MS: 60_000,
  CONFIDENCE_HIGH_MIN: 0.85,
  CONFIDENCE_MEDIUM_MIN: 0.65,
  MOCK_API: false,
};

const finding: components["schemas"]["FindingView"] = {
  account_id: "account-1",
  confidence: 0.9,
  decided_by: "LLM",
  document: {
    id: "document-1",
    language: "de",
    plugin_code: "WEBSITE",
    published_at: null,
    source_type: "COMPANY_PUBLICATION",
    title: "News",
    url: "https://group.example/news",
  },
  feedback: null,
  id: "finding-1",
  observed_at: "2026-09-05T00:00:00Z",
  option: null,
  points: 53,
  question: { id: "question-1", key: "AUTOMATION", polarity: "POSITIVE", text: "Projects?" },
  question_revision: 1,
  quote: "Automatisierung",
  quote_en: "Automation",
  rationale: null,
  service_id: "service-1",
  status: "ACTIVE",
  strength: "STRONG",
};

it("FR-009 FR-010 presents confidence and age with numeric and absolute tooltips", async () => {
  const user = userEvent.setup();
  const observedAt = new Date(finding.observed_at);
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const { container } = render(
    <ConfigProvider value={config}>
      <QuoteBlock finding={finding} now={new Date("2026-09-26T00:00:00Z")} />
    </ConfigProvider>,
  );

  expect(screen.getByText("High")).toBeVisible();
  expect(screen.queryByText("0.9")).not.toBeInTheDocument();
  await user.hover(screen.getByText("High"));
  expect(await screen.findByRole("tooltip")).toHaveTextContent("0.9");

  await user.unhover(screen.getByText("High"));
  await user.hover(screen.getByText("21 days ago"));
  expect(await screen.findByRole("tooltip")).toHaveTextContent(absoluteTooltip(observedAt, timeZone));
  expect((await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations).toEqual([]);
});
