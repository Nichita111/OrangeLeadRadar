import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RowMenu } from "./RowMenu";

describe("RowMenu (FR-020, FR-156)", () => {
  it("opens on click and calls the item's onSelect", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <RowMenu
        label="Actions for Intelligent Automation"
        items={[{ label: "Deactivate", onSelect }]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Actions for Intelligent Automation" }));
    await user.click(await screen.findByRole("menuitem", { name: "Deactivate" }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("a disabled item cannot be selected", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<RowMenu label="Actions" items={[{ label: "Reactivate", onSelect, disabled: true }]} />);
    await user.click(screen.getByRole("button", { name: "Actions" }));
    const item = await screen.findByRole("menuitem", { name: "Reactivate" });
    expect(item).toHaveAttribute("aria-disabled", "true");
    await user.click(item);
    expect(onSelect).not.toHaveBeenCalled();
  });
});
