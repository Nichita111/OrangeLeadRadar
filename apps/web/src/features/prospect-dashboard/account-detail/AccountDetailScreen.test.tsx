import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { errorEnvelope, errorResponse } from "../../../api/authenticationAndUsers.fixtures";
import { http, server } from "../../../testServer";
import { renderAt } from "../testSupport";

describe("AccountDetailScreen", () => {
  it("FR-066: the header shows the account, its parent, band, figures and scoring version", async () => {
    renderAt("/accounts/acc-lh");

    expect(await screen.findByRole("heading", { name: "Lufthansa Group" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "lufthansa.com" })).toHaveAttribute(
      "href",
      "https://lufthansa.com",
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

  it("FR-131, FR-074: Read the evidence opens Signals with the quote highlighted, the original and the GDELT credit", async () => {
    renderAt("/accounts/acc-lh");
    const cost = (await screen.findByText("Cost programme")).closest("li") as HTMLElement;

    fireEvent.click(within(cost).getByRole("link", { name: "Read the evidence" }));

    const mark = await screen.findByText("Wir senken die Kosten um 500 Millionen Euro.", {
      selector: "mark",
    });
    expect(mark).toBeInTheDocument();
    expect(screen.getByText(/Strategy 2030/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open original" })).toHaveAttribute(
      "href",
      "https://gdelt.example/fnd-cost",
    );
    expect(screen.getByText(/Found by the/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GDELT Project" })).toHaveAttribute(
      "href",
      "https://www.gdeltproject.org/",
    );
  });

  it("FR-074: a purged document shows the quote, the link and that the full text is no longer stored", async () => {
    renderAt("/accounts/acc-lh?tab=signals&finding=fnd-inhouse");

    expect(
      await screen.findByText("The full text of this page is no longer stored."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open original" })).toBeInTheDocument();
  });
});
