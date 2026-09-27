import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  expectFullKeyboardCoverage,
  expectNoSalesForbiddenWording,
  expectNoSeriousOrCriticalViolations,
  tabOrderWithin,
} from "../../../accessibilityTestSupport";
import { errorEnvelope, errorResponse } from "../../../api/authenticationAndUsers.fixtures";
import { createAccountsAndDiscoveryHandlers } from "../../../mocks/accountsAndDiscovery";
import { createOutreachAndCrmHandlers } from "../../../mocks/outreachAndCrm";
import { createMockStore } from "../../../mocks/store";
import { http, server } from "../../../testServer";
import { renderAt } from "../testSupport";

describe("AccountDetailScreen", () => {
  it("FR-066: the header shows the account, its parent, band, figures and scoring version", async () => {
    renderAt("/accounts/acc-lh");

    expect(await screen.findByRole("heading", { name: "Lufthansa Group" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "lufthansagroup.com" })).toHaveAttribute(
      "href",
      "https://lufthansagroup.com",
    );
    expect(await screen.findByText("Germany, Aerospace and aviation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lufthansa Holding" })).toHaveAttribute(
      "href",
      "/accounts/acc-holding",
    );
    expect(await screen.findByText("Warm")).toBeInTheDocument();
    expect(screen.getByText(/with scoring version/)).toHaveTextContent("3");
  });

  it("FR-070: the Why tab lists criteria with marks and points, and counted signals with quotes", async () => {
    renderAt("/accounts/acc-lh");

    const sector = (await screen.findByText("Sector")).closest("li") as HTMLElement;
    expect(within(sector).getByLabelText("Matches")).toBeInTheDocument();
    expect(await within(sector).findByText("Aerospace and aviation")).toBeInTheDocument();
    expect(within(sector).getByText("+37.5")).toBeInTheDocument();
    const size = screen.getByText("Size").closest("li") as HTMLElement;
    expect(within(size).getByLabelText("Unknown")).toBeInTheDocument();
    expect(within(size).getByText(/add the employee count/)).toBeInTheDocument();

    const cost = (await screen.findByText("Cost programme")).closest("li") as HTMLElement;
    expect(within(cost).getByText(/Wir senken die Kosten/)).toBeInTheDocument();
    expect(within(cost).getByText(/We are cutting costs/)).toBeInTheDocument();
    expect(within(cost).getByText("+53.0")).toBeInTheDocument();
    expect(within(cost).getByText("1 other signal")).toBeInTheDocument();
    const inHouse = screen.getByText("In-house automation capability").closest("li") as HTMLElement;
    expect(within(inHouse).getByText("-41.4")).toBeInTheDocument();
  });

  it("WF-13: the tabs link to Why, Signals and Outreach of the account", async () => {
    renderAt("/accounts/acc-lh");

    const tabs = await screen.findByRole("navigation", { name: "Account detail tabs" });
    expect(within(tabs).getByRole("link", { name: "Why" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "Signals" })).toHaveAttribute(
      "href",
      "/accounts/acc-lh?tab=signals",
    );
    expect(within(tabs).getByRole("link", { name: "Outreach" })).toHaveAttribute(
      "href",
      "/accounts/acc-lh/outreach",
    );
  });

  it("FR-086: the Outreach tab shows under the header with the account's contacts to address a draft to", async () => {
    const store = createMockStore();
    server.use(
      ...createAccountsAndDiscoveryHandlers(store),
      ...createOutreachAndCrmHandlers(store),
    );
    renderAt("/accounts/acc-lh/outreach");

    expect(await screen.findByRole("heading", { name: "Lufthansa Group" })).toBeInTheDocument();
    const tabs = await screen.findByRole("navigation", { name: "Account detail tabs" });
    expect(within(tabs).getByRole("link", { name: "Outreach" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(tabs).getByRole("link", { name: "Why" })).toHaveAttribute(
      "href",
      "/accounts/acc-lh?tab=why",
    );
    expect(await screen.findByText("Mira Hoffmann")).toBeInTheDocument();
    expect(
      await screen.findByRole("option", {
        name: "Mira Hoffmann — Head of Global Business Services",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate" })).toBeInTheDocument();
    expect(screen.queryByText("Sector")).not.toBeInTheDocument();
  });

  it("FR-071: the matched exclusion rule is listed with the fact that matched", async () => {
    renderAt("/accounts/acc-fr");

    const rule = (await screen.findByText("Outside DACH", { selector: "span" })).closest(
      "li",
    ) as HTMLElement;
    expect(within(rule).getByText(/Region: France/)).toBeInTheDocument();
  });

  it("FR-071, FR-015, S-PRO-05: an Admin adds an exception with a required note and revokes it after confirming", async () => {
    renderAt("/accounts/acc-fr");
    fireEvent.click(await screen.findByRole("button", { name: "Add exception" }));

    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Add exception" }));
    expect(within(dialog).getByText("Enter a note.")).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText("Note"), {
      target: { value: "Region is out of date" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add exception" }));

    await screen.findByText(/is being rescored/);
    expect(await screen.findByText(/Region is out of date/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Revoke exception" }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: "Revoke exception" }));
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Revoke exception" })).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "Add exception" })).toBeInTheDocument();
  });

  it("FR-005, R-2: a failed revoke shows the api's message", async () => {
    renderAt("/accounts/acc-fr");
    server.use(
      http.post("/api/v1/overrides/{id}/revoke", () =>
        errorResponse(errorEnvelope("CONFLICT", "The exception was already revoked."), 409),
      ),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Add exception" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Note"), { target: { value: "Out of date" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add exception" }));
    fireEvent.click(await screen.findByRole("button", { name: "Revoke exception" }));

    fireEvent.click(
      within(await screen.findByRole("alertdialog")).getByRole("button", {
        name: "Revoke exception",
      }),
    );

    expect(await screen.findByText("The exception was already revoked.")).toBeInTheDocument();
  });

  it("FR-005, R-1: a failed API-07 shows the error with Retry, not 'no active service'", async () => {
    renderAt("/accounts/acc-fr");
    server.use(
      http.get("/api/v1/services", () =>
        errorResponse(errorEnvelope("INTERNAL", "Services failed."), 500),
      ),
    );

    expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText("There is no active service yet.")).not.toBeInTheDocument();
  });

  it("FR-071: a Sales user sees neither control", async () => {
    renderAt("/accounts/acc-fr", "SALES");

    await screen.findByText("Outside DACH", { selector: "span" });
    expect(screen.queryByRole("button", { name: "Add exception" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revoke exception" })).not.toBeInTheDocument();
  });

  it("FR-116: each counted signal on the Why tab opens its original in a new tab at the quoted line", async () => {
    renderAt("/accounts/acc-lh");

    const cost = (await screen.findByText("Cost programme")).closest("li") as HTMLElement;
    const original = await within(cost).findByRole("link", { name: "Open original" });
    expect(original).toHaveAttribute(
      "href",
      "https://gdelt.example/fnd-cost#:~:text=Wir%20senken%20die%20Kosten%20um%20500%20Millionen%20Euro.",
    );
    expect(original).toHaveAttribute("target", "_blank");
    expect(within(cost).queryByRole("link", { name: "Read the evidence" })).not.toBeInTheDocument();
  });

  it("FR-074, S-PRO-03: a signal shows its quote, why it counts, Open original and the GDELT credit, and no passage", async () => {
    renderAt("/accounts/acc-lh?tab=signals");

    const quote = await screen.findByText("Wir senken die Kosten um 500 Millionen Euro.");
    const signal = quote.closest("li") as HTMLElement;
    expect(within(signal).getByText(/We are cutting costs/)).toBeInTheDocument();
    expect(
      within(signal).getByText("A group-wide cost programme with a stated target."),
    ).toBeInTheDocument();
    const original = within(signal).getByRole("link", { name: "Open original" });
    expect(original).toHaveAttribute(
      "href",
      "https://gdelt.example/fnd-cost#:~:text=Wir%20senken%20die%20Kosten%20um%20500%20Millionen%20Euro.",
    );
    expect(original).toHaveAttribute("target", "_blank");
    expect(within(signal).getByRole("link", { name: "GDELT Project" })).toHaveAttribute(
      "href",
      "https://www.gdeltproject.org/",
    );
    expect(within(signal).queryByRole("button", { name: "Evidence" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Strategy 2030/)).not.toBeInTheDocument();
  });

  it("FR-074: a signal without a reason shows no Why it counts line", async () => {
    renderAt("/accounts/acc-lh?tab=signals");

    const quote = await screen.findByText("Wir suchen Automatisierungsingenieure.");
    const signal = quote.closest("li") as HTMLElement;
    expect(within(signal).queryByText("Why it counts:")).not.toBeInTheDocument();
    expect(within(signal).queryByText(/GDELT Project/)).not.toBeInTheDocument();
  });
});

describe("Accessibility (N-10, FR-016)", () => {
  it.each(["SALES", "ADMIN"] as const)(
    "has no serious or critical axe violation on the Why tab as %s",
    async (role) => {
      const { container } = renderAt("/accounts/acc-lh", role);
      await screen.findByRole("heading", { name: "Lufthansa Group" });

      await expectNoSeriousOrCriticalViolations(container);
    },
  );

  it.each(["SALES", "ADMIN"] as const)(
    "has no serious or critical axe violation on the Signals tab as %s",
    async (role) => {
      const { container } = renderAt("/accounts/acc-lh?tab=signals", role);
      await screen.findByText("Wir senken die Kosten um 500 Millionen Euro.");

      await expectNoSeriousOrCriticalViolations(container);
    },
  );

  it("tabs through every action of the Why tab with each one taking focus in turn", async () => {
    const { container } = renderAt("/accounts/acc-lh");
    await screen.findByRole("heading", { name: "Lufthansa Group" });

    const visited = await tabOrderWithin(userEvent.setup(), container);

    expectFullKeyboardCoverage(container, visited);
  });

  it("shows Sales no escalation, triage or fixture probability wording on the Why tab", async () => {
    const { container } = renderAt("/accounts/acc-lh", "SALES");
    await screen.findByRole("heading", { name: "Lufthansa Group" });

    expectNoSalesForbiddenWording(container);
  });

  it("shows Sales no escalation, triage or fixture probability wording on the Signals tab", async () => {
    const { container } = renderAt("/accounts/acc-lh?tab=signals", "SALES");
    await screen.findByText("Wir senken die Kosten um 500 Millionen Euro.");

    expectNoSalesForbiddenWording(container);
  });
});
