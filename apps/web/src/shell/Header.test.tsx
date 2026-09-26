import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { Header } from "./Header";
describe("Header", () => {
  it("FR-102 links the parent on Account detail", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/accounts/abc"]}>
        <Header />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Accounts" })).toHaveAttribute("href", "/accounts");
    expect(screen.queryByText("Admin only")).not.toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
  it("FR-102 marks Admin screens", () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <Header />
      </MemoryRouter>,
    );
    expect(screen.getByText("Admin only")).toBeInTheDocument();
  });
});
