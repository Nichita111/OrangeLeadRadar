import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { Navigation } from "./Navigation";

describe("Navigation", () => {
  it("FR-001 FR-101 shows Work to Sales, labels icons, and marks the current page", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/alerts"]}>
        <Navigation userRole="SALES" alertCount={3} />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole("link")).toHaveLength(6);
    expect(screen.queryByText("Admin only")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Alerts/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByLabelText("3 unread alerts")).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("FR-001 shows the six Admin entries to Admins", async () => {
    const { container } = render(
      <MemoryRouter>
        <Navigation userRole="ADMIN" />
      </MemoryRouter>,
    );
    expect(screen.getByText("Admin only")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(12);
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
