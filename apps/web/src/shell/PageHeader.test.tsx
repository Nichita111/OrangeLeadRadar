import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "../components/Button";
import { PageHeader } from "./PageHeader";

describe("PageHeader (FR-103, FR-104)", () => {
  it("shows the title, one lead sentence and at most one primary action", () => {
    render(
      <PageHeader
        title="Users"
        lead="Create the people who can sign in."
        action={<Button variant="primary">New user</Button>}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Users" })).toBeInTheDocument();
    expect(screen.getByText("Create the people who can sign in.")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("renders without an action", () => {
    render(<PageHeader title="Runs" lead="Watch the runs." />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
