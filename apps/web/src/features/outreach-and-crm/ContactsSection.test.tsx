import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, onTestFinished } from "vitest";

import { errorEnvelope, errorResponse } from "../../api/authenticationAndUsers.fixtures";
import { createAccountsAndDiscoveryHandlers } from "../../mocks/accountsAndDiscovery";
import { createOutreachAndCrmHandlers } from "../../mocks/outreachAndCrm";
import { createMockStore } from "../../mocks/store";
import { http, server } from "../../testServer";
import { renderAt } from "../prospect-dashboard/testSupport";

function renderOutreach(accountId: string) {
  const store = createMockStore();
  server.use(...createAccountsAndDiscoveryHandlers(store), ...createOutreachAndCrmHandlers(store));
  renderAt(`/accounts/${accountId}/outreach`);
}

describe("ContactsSection", () => {
  it("FR-189: Suggest contacts lists people with their quote and source, and says nothing is stored until Add", async () => {
    renderOutreach("acc-lh");

    fireEvent.click(await screen.findByRole("button", { name: "Suggest contacts" }));

    const list = await screen.findByRole("region", { name: "Suggested contacts" });
    expect(within(list).getByText(/Nothing is stored until you add a person/)).toBeInTheDocument();
    const brandt = within(list).getByText("Jan-Erik Brandt").closest("li") as HTMLElement;
    expect(within(brandt).getByText("Leiter Prozessexzellenz")).toBeInTheDocument();
    expect(
      within(brandt).getByText(/verantwortet das Programm Fit for Growth/),
    ).toBeInTheDocument();
    expect(within(brandt).getByRole("link", { name: "Fit for Growth" })).toHaveAttribute(
      "href",
      "https://lufthansa.com/newsroom/fit-for-growth",
    );
    expect(within(list).queryByText("Mira Hoffmann")).not.toBeInTheDocument();
  });

  it("FR-189, FR-048: Add adds the suggestion as a contact with its source page and removes it from the list", async () => {
    let created: unknown = null;
    const capture = ({ request }: { request: Request }) => {
      if (request.method === "POST" && request.url.endsWith("/accounts/acc-lh/contacts")) {
        void request
          .clone()
          .json()
          .then((body: unknown) => {
            created = body;
          });
      }
    };
    server.events.on("request:start", capture);
    onTestFinished(() => {
      server.events.removeListener("request:start", capture);
    });
    renderOutreach("acc-lh");
    fireEvent.click(await screen.findByRole("button", { name: "Suggest contacts" }));
    const list = await screen.findByRole("region", { name: "Suggested contacts" });
    const brandt = within(list).getByText("Jan-Erik Brandt").closest("li") as HTMLElement;

    fireEvent.click(within(brandt).getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(within(list).queryByText("Jan-Erik Brandt")).not.toBeInTheDocument();
    });
    expect(created).toEqual({
      full_name: "Jan-Erik Brandt",
      job_title: "Leiter Prozessexzellenz",
      source_url: "https://lufthansa.com/newsroom/fit-for-growth",
    });
    expect(
      await screen.findByRole("option", {
        name: "Jan-Erik Brandt — Leiter Prozessexzellenz",
      }),
    ).toBeInTheDocument();
  });

  it("FR-189: with no suggestion, the list says the stored documents name no one yet", async () => {
    renderOutreach("acc-fr");

    fireEvent.click(await screen.findByRole("button", { name: "Suggest contacts" }));

    expect(
      await screen.findByText("The account's stored documents name no one yet."),
    ).toBeInTheDocument();
  });

  it("FR-005: a failed request shows the api's message", async () => {
    renderOutreach("acc-lh");
    server.use(
      http.post("/api/v1/accounts/{id}/contact-suggestions", () =>
        errorResponse(
          errorEnvelope("BUDGET_EXHAUSTED", "Today's budget for detailed checks is used up."),
          429,
        ),
      ),
    );

    fireEvent.click(await screen.findByRole("button", { name: "Suggest contacts" }));

    expect(
      await screen.findByText("Today's budget for detailed checks is used up."),
    ).toBeInTheDocument();
  });
});
