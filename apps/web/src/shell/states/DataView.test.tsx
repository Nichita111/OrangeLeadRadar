import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { errorEnvelope } from "../../api/authenticationAndUsers.fixtures";
import { ApiError, parseErrorEnvelope } from "../../api/client";
import { DEPENDENCIES } from "../../api/dependencies";
import { Button } from "../../components/Button";
import { DataView, type DataViewQuery } from "./DataView";
import { DEPENDENCY_ROWS, SCREEN_WORDING } from "./degradation";
import { NotAllowed } from "./NotAllowed";
import { NotFound } from "./NotFound";

function renderView(query: DataViewQuery<string[]>) {
  return render(
    <DataView
      query={query}
      isEmpty={(rows) => rows.length === 0}
      skeleton={<div>skeleton rows</div>}
      empty={{
        message: "No users yet. New user creates the first one.",
        action: <Button variant="secondary">New user</Button>,
      }}
    >
      {(rows) => (
        <ul>
          {rows.map((row) => (
            <li key={row}>{row}</li>
          ))}
        </ul>
      )}
    </DataView>,
  );
}

const refetch = vi.fn();

describe("DataView (FR-005, FR-118)", () => {
  it("shows skeletons while loading", () => {
    renderView({ status: "pending", refetch });
    expect(screen.getByText("skeleton rows")).toBeInTheDocument();
  });

  it("shows the empty sentence with its action button", () => {
    renderView({ status: "success", data: [], refetch });
    expect(screen.getByText("No users yet. New user creates the first one.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New user" })).toBeInTheDocument();
  });

  it("shows the data", () => {
    renderView({ status: "success", data: ["Ana"], refetch });
    expect(screen.getByText("Ana")).toBeInTheDocument();
  });

  it("shows the error's message with a Retry that refetches", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    const error = new ApiError(500, errorEnvelope("INTERNAL", "Something went wrong on our side."));
    renderView({ status: "error", error, refetch: retry });
    expect(screen.getByText("Something went wrong on our side.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("shows Not allowed for a 403", () => {
    const error = new ApiError(403, errorEnvelope("FORBIDDEN", "The role does not allow it."));
    render(
      <MemoryRouter>
        <DataView
          query={{ status: "error", error, refetch }}
          isEmpty={() => false}
          skeleton={null}
          empty={{ message: "", action: null }}
        >
          {() => null}
        </DataView>
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
  });

  it("shows a non-api error's message", () => {
    renderView({ status: "error", error: new Error("boom"), refetch });
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it.each(
    DEPENDENCIES.filter((dependency) => dependency !== "DATABASE").map(
      (dependency) => [dependency, DEPENDENCY_ROWS[dependency]] as const,
    ),
  )(
    "503 with dependency %s shows the %s row: the headline in bold, one check per item",
    (dependency, row) => {
      const wording = SCREEN_WORDING[row];
      if (wording === undefined || !("stillWorks" in wording)) {
        throw new Error(`No Still works wording for ${row}`);
      }
      const error = new ApiError(
        503,
        errorEnvelope("UPSTREAM_UNAVAILABLE", "Unavailable.", { dependency }),
      );
      renderView({ status: "error", error, refetch });
      expect(screen.getByText(wording.headline).tagName).toBe("STRONG");
      expect(screen.getByText("Still works")).toBeInTheDocument();
      expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(
        wording.stillWorks,
      );
      expect(document.body).not.toHaveTextContent(/Jev|OpenRouter|LLM|classifier/i);
    },
  );

  it("503 with the Database dependency shows its closing sentence and no check", () => {
    const error = new ApiError(
      503,
      errorEnvelope("UPSTREAM_UNAVAILABLE", "Unavailable.", { dependency: "DATABASE" }),
    );
    renderView({ status: "error", error, refetch });
    expect(screen.getByText("The database is unavailable.").tagName).toBe("STRONG");
    expect(screen.getByText(/Nothing works until it is back\./)).toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toEqual([]);
  });

  it("429 BUDGET_EXHAUSTED, with no dependency, shows the LLM daily budget row", () => {
    const error = new ApiError(
      429,
      errorEnvelope("BUDGET_EXHAUSTED", "The daily budget is reached.", {
        resets_at: "2026-09-27T00:00:00Z",
      }),
    );
    renderView({ status: "error", error, refetch });
    expect(screen.getByText("Today's budget for detailed checks is used up.").tagName).toBe(
      "STRONG",
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("an unknown dependency value shows the error state with its message", () => {
    const envelope = parseErrorEnvelope({
      error: {
        code: "UPSTREAM_UNAVAILABLE",
        message: "Something else is down.",
        details: { dependency: "MYSTERY" },
      },
    });
    if (envelope === null) {
      throw new Error("The body is an envelope.");
    }
    renderView({ status: "error", error: new ApiError(503, envelope), refetch });
    expect(screen.getByText("Something else is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("a 503 whose code is not UPSTREAM_UNAVAILABLE shows the error state with its message", () => {
    const error = new ApiError(503, errorEnvelope("INTERNAL", "Try again later."));
    renderView({ status: "error", error, refetch });
    expect(screen.getByText("Try again later.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("Not allowed and Not found (FR-006, FR-159)", () => {
  it("Not allowed names the Admin role and links to Prospects", () => {
    render(
      <MemoryRouter>
        <NotAllowed />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
    expect(screen.getByText("This page needs the Admin role.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Prospects" })).toHaveAttribute(
      "href",
      "/prospects",
    );
  });

  it("Not found says the page does not exist and links to Prospects", () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByText("This page does not exist.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Prospects" })).toHaveAttribute(
      "href",
      "/prospects",
    );
  });
});
