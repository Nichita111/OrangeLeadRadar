import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  anaSales,
  errorEnvelope,
  errorResponse,
} from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

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

function task(overrides: Partial<Schemas["LabelTask"]> = {}): Schemas["LabelTask"] {
  return {
    chunk_id: "chunk-1",
    passage_text: "Lufthansa Group plans a cost-reduction programme.",
    question: {
      id: "question-1",
      key: "COST_PROGRAM",
      text: "Does the company announce a cost-reduction programme?",
      answer_type: "YES_NO",
      options: null,
      polarity: "POSITIVE",
    },
    question_revision: 1,
    account: { id: "account-1", name: "Lufthansa Group" },
    document: {
      title: "Lufthansa Group streamlines administration",
      url: "https://lufthansagroup.com/press",
      language: "en",
      published_at: "2026-05-01T00:00:00Z",
    },
    ...overrides,
  };
}

function arrange(queue: Schemas["LabelQueue"], services: Schemas["Service"][] = [SERVICE_A]) {
  server.use(
    http.get("/api/v1/services", ({ response }) => response(200).json(services)),
    http.get("/api/v1/evaluation/label-queue", ({ response }) => response(200).json(queue)),
  );
  signedInAs(anaSales);
  return renderApp("/labelling");
}

describe("LabellingScreen", () => {
  it("FR-078: shows question, company, source link, language, age and passage, never the classifier's answer", async () => {
    arrange({ tasks: [task()], active_items: 143, min_items: 200 });

    expect(
      await screen.findByText("Does the company announce a cost-reduction programme?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Lufthansa Group plans a cost-reduction programme."),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Lufthansa Group").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: /Lufthansa Group streamlines administration/ }),
    ).toHaveAttribute("href", "https://lufthansagroup.com/press");
    expect(screen.getByText(/English/)).toBeInTheDocument();
    expect(screen.queryByText(/0\.\d/)).not.toBeInTheDocument();
    expect(screen.queryByText(/p_positive/i)).not.toBeInTheDocument();
  });

  it("FR-079: keys 0 to 3 post NONE/WEAK/MEDIUM/STRONG, and S skips without showing the pair again", async () => {
    const bodies: Schemas["LabelCreate"][] = [];
    const firstTask = task({ chunk_id: "chunk-1", question: { ...task().question, id: "q-1" } });
    const secondTask = task({ chunk_id: "chunk-2", question: { ...task().question, id: "q-2" } });
    arrange({ tasks: [firstTask, secondTask], active_items: 0, min_items: 200 });
    server.use(
      http.post("/api/v1/evaluation/items", async ({ request, response }) => {
        const body = await request.json();
        bodies.push(body);
        return response(200).json({
          id: "item-1",
          chunk_id: body.chunk_id,
          question_id: body.question_id,
          question_revision: body.question_revision,
          created_at: "2026-09-26T00:00:00Z",
          question_key: "COST_PROGRAM",
          expected_strength: body.expected_strength,
          origin: "MANUAL",
          status: "ACTIVE",
          labelled_by_name: "Ana Sales",
        });
      }),
    );

    await screen.findByText(firstTask.passage_text);
    fireEvent.keyDown(window, { key: "s" });

    await screen.findByText(secondTask.passage_text);
    fireEvent.keyDown(window, { key: "3" });

    await waitFor(() => {
      expect(bodies).toHaveLength(1);
    });
    expect(bodies[0]).toMatchObject({ chunk_id: "chunk-2", expected_strength: "STRONG" });
  });

  it("FR-080, FR-144: shows the active count, a progress bar and a callout that the classifier's answer is never shown", async () => {
    arrange({ tasks: [task()], active_items: 143, min_items: 200 });

    expect(await screen.findByText("Labels: 143 of 200 needed")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "143");
    expect(screen.getByText(/classifier's answer is never shown here/)).toBeInTheDocument();
  });

  it("FR-081: shows the empty state with its action when the queue is empty", async () => {
    arrange({ tasks: [], active_items: 0, min_items: 200 });

    expect(await screen.findByText(/There is nothing left to label/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Accounts" })).toHaveAttribute(
      "href",
      "/accounts",
    );
  });

  it("FR-145: shows the legend and a toast before the next task", async () => {
    const first = task({ chunk_id: "chunk-1" });
    arrange({ tasks: [first], active_items: 0, min_items: 200 });
    server.use(
      http.post("/api/v1/evaluation/items", ({ response }) =>
        response(200).json({
          id: "item-1",
          chunk_id: "chunk-1",
          question_id: "question-1",
          question_revision: 1,
          created_at: "2026-09-26T00:00:00Z",
          question_key: "COST_PROGRAM",
          expected_strength: "WEAK",
          origin: "MANUAL",
          status: "ACTIVE",
          labelled_by_name: "Ana Sales",
        }),
      ),
    );

    expect(
      await screen.findByText(/No: no signal\. Weak: mentioned or implied\./),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "[1] Weak" }));

    expect(await screen.findByText("Label saved.")).toBeInTheDocument();
  });

  it("shows an error callout, never a toast, and refetches on a 409", async () => {
    const first = task({ chunk_id: "chunk-1" });
    arrange({ tasks: [first], active_items: 0, min_items: 200 });
    let calls = 0;
    server.use(
      http.post("/api/v1/evaluation/items", () => {
        calls += 1;
        return errorResponse(
          errorEnvelope("CONFLICT", "The question revision is not current."),
          409,
        );
      }),
    );

    expect(await screen.findByText(first.passage_text)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "[0] No" }));

    await waitFor(() => {
      expect(calls).toBe(1);
    });
    expect(screen.queryByText("Label saved.")).not.toBeInTheDocument();
  });

  it("FR-003: requests the queue for the selected service, and again, with the skip set kept, when the selection changes", async () => {
    const requestedServiceIds: string[] = [];
    server.use(
      http.get("/api/v1/services", ({ response }) => response(200).json([SERVICE_A, SERVICE_B])),
      http.get("/api/v1/evaluation/label-queue", ({ request, response }) => {
        const url = new URL(request.url);
        requestedServiceIds.push(url.searchParams.get("service_id") ?? "");
        const serviceId = url.searchParams.get("service_id");
        const chunkId = serviceId === "service-a" ? "chunk-a" : "chunk-b";
        return response(200).json({
          tasks: [task({ chunk_id: chunkId })],
          active_items: 0,
          min_items: 200,
        });
      }),
    );
    signedInAs(anaSales);
    renderApp("/labelling");

    await screen.findByText("Lufthansa Group plans a cost-reduction programme.");
    expect(requestedServiceIds).toContain("service-a");

    fireEvent.change(screen.getByLabelText("Service"), { target: { value: "service-b" } });

    await waitFor(() => {
      expect(requestedServiceIds).toContain("service-b");
    });
  });
});
