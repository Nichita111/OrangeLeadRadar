import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { PageHeader } from "./PageHeader";
describe("PageHeader", () => {
  it("FR-103 FR-104 renders title, lead and one primary action slot", async () => {
    const { container } = render(
      <PageHeader
        title="Prospects"
        lead="Choose who to call next."
        action={<button>Refresh</button>}
      />,
    );
    expect(screen.getByRole("heading", { name: "Prospects" })).toBeInTheDocument();
    expect(screen.getByText("Choose who to call next.")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
