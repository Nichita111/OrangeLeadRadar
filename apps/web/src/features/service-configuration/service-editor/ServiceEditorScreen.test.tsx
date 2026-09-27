import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const SERVICE_ID = "11111111-1111-1111-1111-111111111111";

const automation: Schemas["Service"] = {
  id: SERVICE_ID,
  code: "INTELLIGENT_AUTOMATION",
  name: "Intelligent Automation",
  description: "Finds companies automating processes.",
  value_proposition: "Cuts manual work.",
  status: "ACTIVE",
  active_version: 3,
  draft_version: 4,
  question_count: 2,
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
  hint_terms: ["cost reduction"],
  revision: 2,
  status: "ACTIVE",
  finding_count: 14,
  run_id: null,
};

const automationHiring: Schemas["SignalQuestion"] = {
  id: "aaaaaaaa-2222-2222-2222-222222222222",
  service_id: SERVICE_ID,
  key: "AUTOMATION_HIRING",
  text: "Is the company hiring for automation roles?",
  answer_type: "YES_NO",
  options: null,
  polarity: "POSITIVE",
  source_types: ["JOB_POSTING"],
  hint_terms: [],
  revision: 1,
  status: "ACTIVE",
  finding_count: 6,
  run_id: null,
};

function arrange(service: Schemas["Service"], questions: Schemas["SignalQuestion"][]) {
  server.use(
    http.get("/api/v1/services/{id}", ({ response }) => response(200).json(service)),
    http.get("/api/v1/services/{id}/questions", ({ response }) => response(200).json(questions)),
  );
}

async function openEditor(path = `/services/${SERVICE_ID}`) {
  signedInAs(olgaAdmin);
  const view = renderApp(path);
  await screen.findByRole("heading", { name: "Intelligent Automation", level: 1 });
  return view;
}

describe("ServiceEditorScreen tabs (FR-021)", () => {
  it("Overview shows the code read-only and edits name, description, value proposition", async () => {
    arrange(automation, []);
    await openEditor();
    expect(screen.getByText("INTELLIGENT_AUTOMATION")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Intelligent Automation");
    expect(screen.getByLabelText("Description")).toHaveValue(
      "Finds companies automating processes.",
    );
  });

  it("?tab=questions selects the Signal questions tab", async () => {
    arrange(automation, [costProgram]);
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    expect(screen.getByRole("tab", { name: "Signal questions" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect((await screen.findAllByText("COST_PROGRAM")).length).toBeGreaterThan(0);
  });

  it("the Scoring tab links to the scoring route", async () => {
    arrange(automation, []);
    await openEditor();
    expect(screen.getByRole("tab", { name: "Scoring" })).toHaveAttribute(
      "href",
      `/services/${SERVICE_ID}/scoring`,
    );
  });
});

describe("Signal questions tab (FR-022, FR-150)", () => {
  it("lists questions active first with key, text, answer type and signal count", async () => {
    arrange(automation, [costProgram, automationHiring]);
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    expect(await screen.findAllByText("COST_PROGRAM")).toHaveLength(2);
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("AUTOMATION_HIRING")).toBeInTheDocument();
  });

  it("shows each question's status and source types", async () => {
    const inactiveQuestion: Schemas["SignalQuestion"] = {
      ...automationHiring,
      status: "INACTIVE",
    };
    arrange(automation, [costProgram, inactiveQuestion]);
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await screen.findAllByText("COST_PROGRAM");
    const costRow = screen.getByText(costProgram.text).closest("li");
    const hiringRow = screen.getByText(inactiveQuestion.text).closest("li");
    expect(costRow).not.toBeNull();
    expect(hiringRow).not.toBeNull();
    expect(within(costRow as HTMLElement).getByText("Active")).toBeInTheDocument();
    expect(within(costRow as HTMLElement).getByText("News")).toBeInTheDocument();
    expect(within(hiringRow as HTMLElement).getByText("Inactive")).toBeInTheDocument();
    expect(within(hiringRow as HTMLElement).getByText("Job posting")).toBeInTheDocument();
  });

  it("selecting the first question shows its form at the right, with Yes/no, Scale and Choice labels", async () => {
    arrange(automation, [costProgram]);
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    expect(
      await screen.findByRole("heading", { name: "COST_PROGRAM", level: 3 }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Yes/no")).toBeChecked();
    expect(screen.getByLabelText("Scale")).toBeInTheDocument();
    expect(screen.getByLabelText("Choice")).toBeInTheDocument();
    expect(screen.getByText("Revision 2")).toBeInTheDocument();
  });
});

describe("Try it (FR-027)", () => {
  it("runs the form's unsaved question against pasted text and shows each result", async () => {
    const user = userEvent.setup();
    arrange(automation, [costProgram]);
    let sent: unknown;
    server.use(
      http.post("/api/v1/questions/preview", async ({ request, response }) => {
        sent = await request.json();
        return response(200).json({
          classifier: "JEV",
          results: [
            {
              passage: "We launch a savings programme.",
              document: null,
              p_positive: 0.91,
              escalated: false,
              strength: "STRONG",
              quote: "We launch a savings programme.",
              quote_en: null,
              rationale: null,
            },
          ],
        });
      }),
    );
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await screen.findByRole("heading", { name: "COST_PROGRAM", level: 3 });
    const tryIt = screen.getByRole("region", { name: "Try it" });
    expect(within(tryIt).getByText("Nothing is saved.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Question"), " now?");
    await user.type(within(tryIt).getByLabelText("Text"), "We launch a savings programme.");
    await user.click(within(tryIt).getByRole("button", { name: "Try it" }));
    expect(
      await within(tryIt).findByText(/We launch a savings programme/, { selector: "blockquote" }),
    ).toBeInTheDocument();
    expect(sent).toMatchObject({
      service_id: SERVICE_ID,
      question_id: costProgram.id,
      text: `${costProgram.text} now?`,
      answer_type: "YES_NO",
      source_types: ["NEWS"],
      sample_text: "We launch a savings programme.",
    });
  });
});

describe("Question form validation and revision (FR-023, FR-024, FR-025)", () => {
  it("a 422 on options/0/strength is placed beside that option's strength control", async () => {
    const user = userEvent.setup();
    const choiceQuestion: Schemas["SignalQuestion"] = {
      ...costProgram,
      answer_type: "CHOICE",
      options: [
        { key: "YES", label: "Yes", strength: "STRONG" },
        { key: "NO", label: "No", strength: "NONE" },
      ],
    };
    arrange(automation, [choiceQuestion]);
    server.use(
      http.patch("/api/v1/questions/{id}", () =>
        Response.json(
          {
            error: {
              code: "VALIDATION",
              message: "The input is invalid.",
              details: {
                fields: [{ field: "/options/0/strength", message: "strength must be valid." }],
              },
            },
          },
          { status: 422 },
        ),
      ),
    );
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await screen.findByRole("heading", { name: "COST_PROGRAM", level: 3 });
    const text = screen.getByLabelText("Question");
    await user.type(text, "?");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("strength must be valid.")).toBeInTheDocument();
  });

  it("warns before Save when the change increments the revision", async () => {
    const user = userEvent.setup();
    arrange(automation, [costProgram]);
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await screen.findByRole("heading", { name: "COST_PROGRAM", level: 3 });
    expect(
      screen.queryByText("Saving will increment the revision and re-check stored data."),
    ).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Question"), "?");
    expect(
      await screen.findByText("Saving will increment the revision and re-check stored data."),
    ).toBeInTheDocument();
  });

  it("shows the new revision and a link to the run after a save that queues one", async () => {
    const user = userEvent.setup();
    arrange(automation, [costProgram]);
    server.use(
      http.patch("/api/v1/questions/{id}", ({ response }) =>
        response(200).json({
          ...costProgram,
          text: "Does the company announce a cost-reduction programme, updated?",
          revision: 3,
          run_id: "bbbbbbbb-1111-1111-1111-111111111111",
        }),
      ),
    );
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await screen.findByRole("heading", { name: "COST_PROGRAM", level: 3 });
    await user.type(screen.getByLabelText("Question"), " updated?");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(
        screen.getAllByRole("status").some((el) => el.textContent.includes("Revision 3 saved")),
      ).toBe(true);
    });
    expect(await screen.findByRole("link", { name: "View the run" })).toHaveAttribute(
      "href",
      "/runs?run=bbbbbbbb-1111-1111-1111-111111111111",
    );
  });

  it("keeps the run link after Add question switches the form into Edit (R-6)", async () => {
    const user = userEvent.setup();
    const created = {
      ...automationHiring,
      revision: 1,
      run_id: "cccccccc-1111-1111-1111-111111111111",
    };
    const questions = [costProgram];
    server.use(
      http.get("/api/v1/services/{id}", ({ response }) => response(200).json(automation)),
      http.get("/api/v1/services/{id}/questions", ({ response }) => response(200).json(questions)),
      http.post("/api/v1/services/{id}/questions", ({ response }) => {
        questions.push(created);
        return response(200).json(created);
      }),
    );
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await screen.findByRole("heading", { name: "COST_PROGRAM", level: 3 });
    await user.click(screen.getByRole("button", { name: "Add question" }));
    await screen.findByRole("heading", { name: "New question", level: 3 });
    await user.type(screen.getByLabelText("Key"), "automation hiring");
    await user.type(screen.getByLabelText("Question"), "Is the company hiring?");
    await user.click(screen.getByRole("checkbox", { name: "Job posting" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    // The saved question replaces "New question" with its own key: the form remounted.
    await screen.findByRole("heading", { name: "AUTOMATION_HIRING", level: 3 });
    expect(await screen.findByRole("link", { name: "View the run" })).toHaveAttribute(
      "href",
      "/runs?run=cccccccc-1111-1111-1111-111111111111",
    );
  });
});

describe("Deactivate and Reactivate (FR-026)", () => {
  it("Deactivate confirms before sending status INACTIVE", async () => {
    const user = userEvent.setup();
    arrange(automation, [costProgram]);
    const bodies: Schemas["SignalQuestionUpdate"][] = [];
    server.use(
      http.patch("/api/v1/questions/{id}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...costProgram, status: "INACTIVE" });
      }),
    );
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await user.click(await screen.findByRole("button", { name: "Actions for COST_PROGRAM" }));
    await user.click(await screen.findByRole("menuitem", { name: "Deactivate" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Deactivate question" });
    expect(dialog).toHaveTextContent("signals stop counting once scoring without it is activated.");
    await user.click(within(dialog).getByRole("button", { name: "Deactivate question" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "INACTIVE" }]);
    });
  });

  it("a failed Deactivate shows an error callout instead of failing silently", async () => {
    const user = userEvent.setup();
    arrange(automation, [costProgram]);
    server.use(
      http.patch("/api/v1/questions/{id}", () =>
        Response.json(
          { error: { code: "CONFLICT", message: "The question could not be deactivated." } },
          { status: 409 },
        ),
      ),
    );
    await openEditor(`/services/${SERVICE_ID}?tab=questions`);
    await user.click(await screen.findByRole("button", { name: "Actions for COST_PROGRAM" }));
    await user.click(await screen.findByRole("menuitem", { name: "Deactivate" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Deactivate question" });
    await user.click(within(dialog).getByRole("button", { name: "Deactivate question" }));
    expect(await screen.findByText("The question could not be deactivated.")).toBeInTheDocument();
  });
});
