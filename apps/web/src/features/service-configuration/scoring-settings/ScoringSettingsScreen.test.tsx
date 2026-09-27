import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const SERVICE_ID = "11111111-1111-1111-1111-111111111111";
const ACTIVE_ID = "22222222-2222-2222-2222-222222222222";
const DRAFT_ID = "33333333-3333-3333-3333-333333333333";
const RUN_ID = "44444444-4444-4444-4444-444444444444";

const service: Schemas["Service"] = {
  id: SERVICE_ID,
  code: "INTELLIGENT_AUTOMATION",
  name: "Intelligent Automation",
  description: "d",
  value_proposition: "v",
  status: "ACTIVE",
  active_version: 3,
  draft_version: 4,
  question_count: 1,
};

function baseSettings(
  overrides: Partial<Schemas["ScoringSettings"]> = {},
): Schemas["ScoringSettings"] {
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
    questions: [{ question_key: "COST_PROGRAM", weight: "MEDIUM", half_life_days: null }],
    disqualifiers: [],
    ...overrides,
  };
}

const activeSummary: Schemas["ScoringConfigSummary"] = {
  id: ACTIVE_ID,
  service_id: SERVICE_ID,
  version: 3,
  status: "ACTIVE",
  change_note: "Went live.",
  activated_at: "2026-09-01T10:00:00Z",
  activated_by_name: "Olga Admin",
};

const draftSummary: Schemas["ScoringConfigSummary"] = {
  id: DRAFT_ID,
  service_id: SERVICE_ID,
  version: 4,
  status: "DRAFT",
  change_note: null,
  activated_at: null,
  activated_by_name: null,
};

const costProgram: Schemas["SignalQuestion"] = {
  id: "aaaaaaaa-1111-1111-1111-111111111111",
  service_id: SERVICE_ID,
  key: "COST_PROGRAM",
  text: "Does the company announce a cost-reduction programme?",
  answer_type: "YES_NO",
  options: null,
  polarity: "POSITIVE",
  source_types: ["NEWS"],
  hint_terms: [],
  revision: 1,
  status: "ACTIVE",
  finding_count: 14,
  run_id: null,
};

function arrange(options: {
  versions: Schemas["ScoringConfigSummary"][];
  configs: Record<string, Schemas["ScoringConfig"]>;
}) {
  server.use(
    http.get("/api/v1/services/{id}", ({ response }) => response(200).json(service)),
    http.get("/api/v1/services/{id}/questions", ({ response }) =>
      response(200).json([costProgram]),
    ),
    http.get("/api/v1/industries", ({ response }) => response(200).json([])),
    http.get("/api/v1/markets", ({ response }) => response(200).json([])),
    http.get("/api/v1/services/{id}/scoring-configs", ({ response }) =>
      response(200).json(options.versions),
    ),
    http.get("/api/v1/scoring-configs/{id}", ({ params, response }) => {
      const config = options.configs[params.id];
      if (config === undefined) {
        throw new Error(`no fixture config for ${params.id}`);
      }
      return response(200).json(config);
    }),
  );
}

async function openScreen() {
  signedInAs(olgaAdmin);
  const view = renderApp(`/services/${SERVICE_ID}/scoring`);
  await screen.findByRole("heading", { name: "Intelligent Automation", level: 1 });
  return view;
}

describe("ScoringSettingsScreen base and unsaved mark (FR-028)", () => {
  it("edits the draft when one exists, and marks unsaved changes", async () => {
    const user = userEvent.setup();
    arrange({
      versions: [activeSummary, draftSummary],
      configs: {
        [DRAFT_ID]: { ...draftSummary, settings: baseSettings() },
        [ACTIVE_ID]: { ...activeSummary, settings: baseSettings() },
      },
    });
    await openScreen();
    expect(await screen.findByText("draft v4")).toBeInTheDocument();
    expect(screen.getByText("v3 active")).toBeInTheDocument();
    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "30%" }));
    expect(await screen.findByText("Unsaved changes")).toBeInTheDocument();
  });
});

describe("Balance (FR-029, FR-151)", () => {
  it("shows Intent share as the complement and an off-set value as a selected extra choice", async () => {
    arrange({
      versions: [activeSummary, draftSummary],
      configs: {
        [DRAFT_ID]: {
          ...draftSummary,
          settings: baseSettings({ fit_weight: 0.45, intent_weight: 0.55 }),
        },
        [ACTIVE_ID]: { ...activeSummary, settings: baseSettings() },
      },
    });
    await openScreen();
    expect(await screen.findByText("Intent share 55%")).toBeInTheDocument();
    const fitShareButton = screen.getByRole("button", { name: "45%" });
    expect(fitShareButton).toHaveAttribute("aria-pressed", "true");
  });
});

describe("Save draft validation (FR-034, AC-05)", () => {
  it("places each violation at its JSON pointer", async () => {
    const user = userEvent.setup();
    arrange({
      versions: [draftSummary],
      configs: { [DRAFT_ID]: { ...draftSummary, settings: baseSettings() } },
    });
    server.use(
      http.put("/api/v1/services/{id}/scoring-configs/draft", () =>
        Response.json(
          {
            error: {
              code: "VALIDATION",
              message: "The input is invalid.",
              details: {
                fields: [
                  {
                    field: "/intent_weight",
                    message: "fit_weight and intent_weight must add up to 1.",
                  },
                  {
                    field: "/warm_threshold",
                    message: "warm_threshold must be less than hot_threshold.",
                  },
                  {
                    field: "/disqualifiers/0/question_key",
                    message: "question_key must name an existing question.",
                  },
                ],
              },
            },
          },
          { status: 422 },
        ),
      ),
    );
    await openScreen();
    await screen.findByText("draft v4");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(
      await screen.findByText("fit_weight and intent_weight must add up to 1."),
    ).toBeInTheDocument();
    expect(screen.getByText("warm_threshold must be less than hot_threshold.")).toBeInTheDocument();
  });
});

describe("Activate (FR-036, G1 b)", () => {
  it("is disabled with unsaved changes, and reads the RESCORE run through API-34 after API-18", async () => {
    const user = userEvent.setup();
    arrange({
      versions: [activeSummary, draftSummary],
      configs: {
        [DRAFT_ID]: { ...draftSummary, settings: baseSettings() },
        [ACTIVE_ID]: { ...activeSummary, settings: baseSettings() },
      },
    });
    await openScreen();
    await screen.findByText("draft v4");
    expect(screen.getByRole("button", { name: "Activate…" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "30%" }));
    expect(screen.getByRole("button", { name: "Activate…" })).toBeDisabled();

    server.use(
      http.get("/api/v1/scoring-configs/{id}", ({ params, response }) =>
        params.id === DRAFT_ID
          ? response(200).json({
              ...draftSummary,
              settings: baseSettings({ fit_weight: 0.3, intent_weight: 0.7 }),
            })
          : response(200).json({ ...activeSummary, settings: baseSettings() }),
      ),
      http.put("/api/v1/services/{id}/scoring-configs/draft", ({ response }) =>
        response(200).json({
          ...draftSummary,
          settings: baseSettings({ fit_weight: 0.3, intent_weight: 0.7 }),
        }),
      ),
    );
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Activate…" })).toBeEnabled();
    });

    server.use(
      http.post("/api/v1/scoring-configs/{id}/activate", ({ response }) =>
        response(200).json({
          id: DRAFT_ID,
          service_id: SERVICE_ID,
          version: 4,
          status: "ACTIVE",
          change_note: "Go live",
          activated_at: "2026-09-27T00:00:00Z",
          activated_by_name: "Olga Admin",
          settings: baseSettings({ fit_weight: 0.3, intent_weight: 0.7 }),
        }),
      ),
      http.get("/api/v1/runs", ({ request, response }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("kind")).toBe("RESCORE");
        expect(url.searchParams.get("service_id")).toBe(SERVICE_ID);
        return response(200).json({
          items: [
            {
              id: RUN_ID,
              kind: "RESCORE",
              trigger: "SCORING_ACTIVATION",
              status: "RUNNING",
              stage: null,
              progress: {},
              errors: [],
              account: null,
              service: { id: SERVICE_ID, name: service.name },
              question: null,
              requested_by_name: "Olga Admin",
              created_at: "2026-09-27T00:00:00Z",
              started_at: "2026-09-27T00:00:00Z",
              finished_at: null,
              ai_cost_eur: 0,
            },
          ],
          page: 1,
          page_size: 50,
          total: 1,
        });
      }),
      http.get("/api/v1/runs/{id}", ({ response }) =>
        response(200).json({
          id: RUN_ID,
          kind: "RESCORE",
          trigger: "SCORING_ACTIVATION",
          status: "SUCCEEDED",
          stage: null,
          progress: {},
          errors: [],
          account: null,
          service: { id: SERVICE_ID, name: service.name },
          question: null,
          requested_by_name: "Olga Admin",
          created_at: "2026-09-27T00:00:00Z",
          started_at: "2026-09-27T00:00:00Z",
          finished_at: "2026-09-27T00:01:00Z",
          ai_cost_eur: 0,
        }),
      ),
    );
    await user.click(screen.getByRole("button", { name: "Activate…" }));
    const dialog = await screen.findByRole("dialog", { name: "Activate this draft" });
    expect(
      within(dialog).getByText(
        "Every score of the service will be recomputed from stored signals.",
      ),
    ).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Change note"), "Go live");
    await user.click(within(dialog).getByRole("button", { name: "Activate" }));
    expect(await within(dialog).findByRole("link", { name: "View the run" })).toHaveAttribute(
      "href",
      `/runs?run=${RUN_ID}`,
    );
    await waitFor(() => {
      expect(within(dialog).getByText(/succeeded/i)).toBeInTheDocument();
    });
  });
});

describe("Versions (FR-037)", () => {
  it("opens a read-only view of the active version, with Back to draft", async () => {
    const user = userEvent.setup();
    arrange({
      versions: [activeSummary, draftSummary],
      configs: {
        [DRAFT_ID]: { ...draftSummary, settings: baseSettings() },
        [ACTIVE_ID]: { ...activeSummary, settings: baseSettings() },
      },
    });
    await openScreen();
    await screen.findByText("draft v4");
    await user.click(screen.getByRole("button", { name: /v3/ }));
    expect(await screen.findByText("Version 3 (ACTIVE)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to draft" }));
    expect(await screen.findByRole("button", { name: "Save draft" })).toBeEnabled();
  });
});
