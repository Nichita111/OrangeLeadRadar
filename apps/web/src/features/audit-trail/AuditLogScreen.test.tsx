import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { olgaAdmin } from "../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../api/contract";
import { renderApp, signedInAs } from "../../testRender";
import { http, server } from "../../testServer";

const entry: Schemas["AuditEntry"] = {
  id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a2a01",
  kind: "USER",
  action: "USER_CREATED",
  actor_name: "Olga Admin",
  entity_type: "user",
  entity_id: null,
  run_id: null,
  request_id: null,
  occurred_at: "2026-09-01T08:00:00Z",
  payload: { role: "SALES" },
};

function arrangeAudit(items: Schemas["AuditEntry"][]): string[] {
  const urls: string[] = [];
  server.use(
    http.get("/api/v1/audit", ({ request, response }) => {
      urls.push(request.url);
      return response(200).json({ items, total: items.length, page: 1, page_size: 50 });
    }),
    http.get("/api/v1/users", ({ response }) => response(200).json([olgaAdmin])),
  );
  return urls;
}

describe("Audit log (FR-098, FR-099)", () => {
  it("lists When, Who, Action and Subject and expands a row to its payload", async () => {
    arrangeAudit([entry]);
    signedInAs(olgaAdmin);
    renderApp("/audit");
    await screen.findByRole("heading", { name: "Audit log", level: 1 });
    const row = await screen.findByRole("row", { name: /User created/ });
    expect(row).toHaveTextContent("Olga Admin");
    expect(row).toHaveTextContent("Sales");
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    expect(await screen.findByText(/"role": "SALES"/)).toBeInTheDocument();
  });

  it("puts the AI calls tab in the URL and in the API-60 query", async () => {
    const urls = arrangeAudit([entry]);
    signedInAs(olgaAdmin);
    const { router } = renderApp("/audit");
    await screen.findByRole("row", { name: /User created/ });
    fireEvent.click(screen.getByRole("button", { name: "AI calls" }));
    await waitFor(() => {
      expect(router.state.location.search).toContain("kind=AI_CALL");
    });
    await waitFor(() => {
      expect(urls.some((url) => url.includes("kind=AI_CALL"))).toBe(true);
    });
  });

  it("says so when no entry matches", async () => {
    arrangeAudit([]);
    signedInAs(olgaAdmin);
    renderApp("/audit");
    expect(await screen.findByText("No audit entries match these filters.")).toBeInTheDocument();
  });
});
