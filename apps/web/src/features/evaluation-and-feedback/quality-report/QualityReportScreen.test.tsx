import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  expectFullKeyboardCoverage,
  expectNoSeriousOrCriticalViolations,
  tabOrderWithin,
} from "../../../accessibilityTestSupport";
import { olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const RUN_ID = "11111111-1111-1111-1111-111111111111";

const SERVICE_A: Schemas["Service"] = {
  id: "service-a",
  code: "INTELLIGENT_AUTOMATION",
  name: "Intelligent Automation",
  description: "d",
  value_proposition: "v",
  status: "ACTIVE",
  active_version: 1,
  draft_version: null,
  question_count: 1,
};

const SERVICE_B: Schemas["Service"] = {
  ...SERVICE_A,
  id: "service-b",
  code: "CYBERSECURITY",
  name: "Cybersecurity services",
};

function emptyPage(): Schemas["Page_Run_"] {
  return { items: [], page: 1, page_size: 50, total: 0 };
}

function run(overrides: Partial<Schemas["Run"]> = {}): Schemas["Run"] {
  return {
    id: RUN_ID,
    kind: "EVALUATION",
    trigger: "USER",
    status: "SUCCEEDED",
    stage: null,
    progress: {},
    errors: [],
    account: null,
    service: null,
    question: null,
    requested_by_name: "Olga Admin",
    created_at: "2026-09-26T10:00:00Z",
    started_at: "2026-09-26T10:00:00Z",
    finished_at: "2026-09-26T10:05:00Z",
    ai_cost_eur: 0.5,
    ...overrides,
  };
}

function summary(
  overrides: Partial<Schemas["EvaluationResultSummary"]> = {},
): Schemas["EvaluationResultSummary"] {
  return {
    run_id: RUN_ID,
    created_at: "2026-09-26T10:05:00Z",
    classifier: "LLM",
    items: 210,
    passed: true,
    precision: 0.85,
    recall: 0.7,
    escalation_rate: 0.12,
    ...overrides,
  };
}

function result(overrides: Partial<Schemas["EvaluationResult"]> = {}): Schemas["EvaluationResult"] {
  return {
    ...summary(),
    escalation_lower: 0.35,
    escalation_upper: 0.65,
    min_precision: 0.8,
    min_items: 200,
    escalation_rate_target: 0.15,
    metrics: {
      items: 210,
      tp: 40,
      fp: 5,
      tn: 150,
      fn: 15,
      precision: 0.85,
      recall: 0.7,
      strength_agreement: 0.6,
      escalation_rate: 0.12,
      classifier_only: { precision: 0.6, recall: 0.5 },
      per_question: {
        "question-1": {
          key: "COST_PROGRAM",
          service_id: "service-a",
          items: 100,
          precision: 0.9,
          recall: 0.8,
        },
        "question-2": {
          key: "INSOLVENCY",
          service_id: "service-b",
          items: 50,
          precision: 0.5,
          recall: 0.4,
        },
      },
      per_source_type: { NEWS: { items: 150, precision: 0.85, recall: 0.7 } },
      missed_evidence: { items: 3, positive_rate: 0.33 },
      calibration: [
        { count: 10, mean_p: 0.05, positive_rate: 0.1 },
        { count: 0, mean_p: null, positive_rate: null },
      ],
      errors: [
        {
          item_id: "item-1",
          expected: "STRONG",
          predicted: "NONE",
          p_positive: 0.2,
          escalated: false,
          question_key: "COST_PROGRAM",
          passage_text: "A missed passage.",
          document: { title: "A title", url: "https://example.com/a" },
        },
      ],
      lead_verdicts: { HOT: { RELEVANT: 3, NOT_RELEVANT: 1 } },
    },
    ...overrides,
  };
}

function impact(overrides: Partial<Schemas["Impact"]> = {}): Schemas["Impact"] {
  return {
    period_days: 30,
    accounts_refreshed: 10,
    refreshes: 12,
    cost_per_refresh_eur: 1.5,
    minutes_per_refresh: 6,
    findings_created: 40,
    precision: 0.85,
    labelled_items: 210,
    manual_minutes_per_account: 120,
    manual_hours_replaced: 20,
    ...overrides,
  };
}

function arrange({
  latestRun = emptyPage(),
  results = [summary()],
  resultDetail = result(),
  impactData = impact(),
  services = [SERVICE_A, SERVICE_B],
}: {
  latestRun?: Schemas["Page_Run_"];
  results?: Schemas["EvaluationResultSummary"][];
  resultDetail?: Schemas["EvaluationResult"];
  impactData?: Schemas["Impact"];
  services?: Schemas["Service"][];
} = {}) {
  server.use(
    http.get("/api/v1/services", ({ response }) => response(200).json(services)),
    http.get("/api/v1/runs", ({ response }) => response(200).json(latestRun)),
    http.get("/api/v1/evaluation/results", ({ response }) => response(200).json(results)),
    http.get("/api/v1/evaluation/results/{run_id}", ({ response }) =>
      response(200).json(resultDetail),
    ),
    http.get("/api/v1/impact", ({ response }) => response(200).json(impactData)),
  );
  signedInAs(olgaAdmin);
  return renderApp("/quality");
}

describe("QualityReportScreen", () => {
  it("FR-083, FR-146: shows the pass sentence, the gate values and their meanings", async () => {
    arrange();

    expect(
      await screen.findByText(/This quality check passes the release gate\./),
    ).toBeInTheDocument();
    expect(screen.getByText("Minimum precision").nextElementSibling).toHaveTextContent("80%");
    const precisionLabel = screen.getAllByText("Precision").find((node) => node.tagName === "DT");
    expect(precisionLabel?.nextElementSibling).toHaveTextContent("85%");
    expect(
      screen.getByText(
        /Of the pairs predicted positive, the share a person also labelled positive\./,
      ),
    ).toBeInTheDocument();
  });

  it("FR-084, FR-147: the per-question table names each question's service and flags precision below the gate", async () => {
    arrange();

    const costProgramRow = (await screen.findByText("COST_PROGRAM")).closest("tr");
    expect(costProgramRow?.textContent).toContain("Intelligent Automation");
    const insolvencyRow = screen.getByText("INSOLVENCY").closest("tr");
    expect(insolvencyRow).not.toBeNull();
    expect(insolvencyRow?.textContent).toContain("Cybersecurity services");
    expect(insolvencyRow?.textContent).toContain("Below the gate");
  });

  it("FR-084, FR-148: shows the calibration chart, mistakes with a document link and lead verdict bars", async () => {
    arrange();

    expect(await screen.findByRole("img", { name: "Calibration chart" })).toBeInTheDocument();
    expect(screen.getByText("A missed passage.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "A title" })).toHaveAttribute(
      "href",
      "https://example.com/a",
    );
    expect(screen.getByText("Relevant 3")).toBeInTheDocument();
    expect(screen.getByText("Not relevant 1")).toBeInTheDocument();
  });

  it("FR-085: history opens a run", async () => {
    const olderId = "22222222-2222-2222-2222-222222222222";
    const older = summary({ run_id: olderId, passed: false });
    server.use(
      http.get("/api/v1/runs", ({ response }) => response(200).json(emptyPage())),
      http.get("/api/v1/evaluation/results", ({ response }) =>
        response(200).json([summary(), older]),
      ),
      http.get("/api/v1/evaluation/results/{run_id}", ({ params, response }) =>
        response(200).json(
          params.run_id === olderId ? result({ ...older, passed: false }) : result(),
        ),
      ),
      http.get("/api/v1/impact", ({ response }) => response(200).json(impact())),
    );
    signedInAs(olgaAdmin);
    const { router } = renderApp("/quality");

    await screen.findByText(/This quality check passes the release gate\./);
    fireEvent.click(screen.getByText(/Failed/));

    await waitFor(() => {
      expect(router.state.location.search).toContain(`run=${olderId}`);
    });
    expect(
      await screen.findByText(/This quality check does not pass the release gate\./),
    ).toBeInTheDocument();
  });

  it("FR-157: shows the Impact values, names the assumption and the closing sentence", async () => {
    arrange();

    expect(
      await screen.findByText(/Manual minutes per account \(assumption\)/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Researching one account by hand takes 120 minutes; LeadRadar refreshed 10 accounts at €1\.50 and 6\.0 minutes each, finding 40 signals, at 85% precision on 210 labelled passages\./,
      ),
    ).toBeInTheDocument();
  });

  it("FR-157: Impact nulls render without inventing a value", async () => {
    arrange({
      impactData: impact({
        cost_per_refresh_eur: null,
        minutes_per_refresh: null,
        precision: null,
        labelled_items: null,
        accounts_refreshed: 0,
        refreshes: 0,
      }),
    });

    expect(
      await screen.findByText(/Researching one account by hand takes 120 minutes/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("FR-082: disables the button and shows the stage while a check found on load is running", async () => {
    const runningRun = run({ status: "RUNNING", stage: "CLASSIFY" });
    server.use(http.get("/api/v1/runs/{id}", ({ response }) => response(200).json(runningRun)));
    arrange({
      latestRun: { items: [runningRun], page: 1, page_size: 50, total: 1 },
    });

    expect(await screen.findByRole("button", { name: /Running · Classify…/ })).toBeDisabled();
  });

  it("FR-082: posting API-53 disables the button until the run is final, then refreshes the results", async () => {
    let getRunCalls = 0;
    server.use(
      http.post("/api/v1/evaluation/runs", ({ response }) =>
        response(202).json(run({ status: "QUEUED" })),
      ),
      http.get("/api/v1/runs/{id}", ({ response }) => {
        getRunCalls += 1;
        return response(200).json(
          run({ status: getRunCalls < 2 ? "RUNNING" : "SUCCEEDED", stage: "CLASSIFY" }),
        );
      }),
    );
    arrange();

    const button = await screen.findByRole("button", { name: "Run quality check" });
    fireEvent.click(button);

    expect(await screen.findByRole("button", { name: /Running/ })).toBeDisabled();
    await waitFor(
      () => {
        expect(screen.getByRole("button", { name: "Run quality check" })).not.toBeDisabled();
      },
      { timeout: 3000 },
    );
  });

  it("shows an error callout, not a toast, when the run fails", async () => {
    server.use(
      http.post("/api/v1/evaluation/runs", ({ response }) =>
        response(202).json(run({ status: "QUEUED" })),
      ),
      http.get("/api/v1/runs/{id}", ({ response }) =>
        response(200).json(
          run({
            status: "FAILED",
            errors: [
              {
                stage: "CLASSIFY",
                code: "UPSTREAM_UNAVAILABLE",
                message: "The classifier is unavailable.",
              },
            ],
          }),
        ),
      ),
    );
    arrange();

    fireEvent.click(await screen.findByRole("button", { name: "Run quality check" }));

    expect(await screen.findByText("The quality check failed.")).toBeInTheDocument();
    expect(screen.getByText("The classifier is unavailable.")).toBeInTheDocument();
  });
});

describe("Accessibility (N-10, FR-016)", () => {
  it("has no serious or critical axe violation as Admin", async () => {
    const { container } = arrange();
    await screen.findByRole("heading", { name: "Quality report", level: 1 });

    await expectNoSeriousOrCriticalViolations(container);
  });

  it("tabs through every action with each one taking focus in turn", async () => {
    const { container } = arrange();
    await screen.findByRole("heading", { name: "Quality report", level: 1 });

    const visited = await tabOrderWithin(userEvent.setup(), container);

    expectFullKeyboardCoverage(container, visited);
  });
});
