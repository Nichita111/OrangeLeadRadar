import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { ApiError } from "../../api/errors";
import { DataState } from "./DataState";

const base = {
  emptyHeadline: "No accounts",
  emptySentence: "Imported accounts appear here.",
  emptyAction: "Import accounts",
  onEmptyAction: vi.fn(),
  retry: vi.fn(),
  children: <p>Rows</p>,
};
describe("DataState", () => {
  it("FR-005 renders loading and empty states", () => {
    const { rerender } = render(<DataState {...base} loading error={undefined} empty={false} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    rerender(<DataState {...base} loading={false} error={undefined} empty />);
    fireEvent.click(screen.getByRole("button", { name: "Import accounts" }));
    expect(base.onEmptyAction).toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "No accounts" }).querySelector("span")).not.toBeNull();
  });
  it("FR-005 shows the error message and retries", () => {
    render(<DataState {...base} loading={false} error={new Error("Try later")} empty={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(screen.getByText("Try later")).toBeInTheDocument();
    expect(base.retry).toHaveBeenCalled();
  });
  it("FR-118 names a 503 dependency and what still works", () => {
    render(
      <DataState
        {...base}
        loading={false}
        error={
          new ApiError(503, {
            code: "UPSTREAM_UNAVAILABLE",
            message: "Classifier failed",
            details: { dependency: "classifier" },
          })
        }
        empty={false}
      />,
    );
    expect(screen.getByText("The classifier is unavailable")).toBeInTheDocument();
    expect(screen.getByText("Scoring from existing findings")).toBeInTheDocument();
  });
  it("FR-118 shows the budget degradation row", () => {
    render(
      <DataState
        {...base}
        loading={false}
        error={new ApiError(429, { code: "BUDGET_EXHAUSTED", message: "Budget reached" })}
        empty={false}
      />,
    );
    expect(screen.getByText("Classification by Jev")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <DataState {...base} loading={false} error={undefined} empty />,
    );
    expect((await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations).toEqual([]);
  });
});
