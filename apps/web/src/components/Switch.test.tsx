import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { Switch } from "./Switch";

describe("Switch (FR-016, Visual language switch radius)", () => {
  it("role=switch carries aria-checked reflecting the value", () => {
    const { rerender } = render(
      <Switch checked={false} onChange={() => undefined} label="Enabled, GDELT" />,
    );
    const control = screen.getByRole("switch", { name: "Enabled, GDELT" });
    expect(control).toHaveAttribute("aria-checked", "false");

    rerender(<Switch checked={true} onChange={() => undefined} label="Enabled, GDELT" />);
    expect(control).toHaveAttribute("aria-checked", "true");
  });

  it("Space and Enter toggle it", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Enabled, GDELT" />);
    const control = screen.getByRole("switch", { name: "Enabled, GDELT" });
    control.focus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it("a disabled switch does not call onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Enabled, GDELT" disabled />);
    await user.click(screen.getByRole("switch", { name: "Enabled, GDELT" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("has no axe violation", async () => {
    const { container } = render(
      <Switch checked={true} onChange={() => undefined} label="Enabled, GDELT" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
