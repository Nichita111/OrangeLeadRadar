import { GearIcon } from "@phosphor-icons/react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button, IconButton } from "./Button";

describe("Button (FR-104, FR-110, FR-016)", () => {
  it("FR-110: the icon-only variant has an accessible name and shows a tooltip on focus", async () => {
    const user = userEvent.setup();
    render(
      <IconButton label="Sign out" icon={<GearIcon aria-hidden />} onClick={() => undefined} />,
    );
    await user.tab();
    expect(screen.getByRole("button", { name: "Sign out" })).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Sign out");
  });

  it("FR-016: works with Enter and Space", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<IconButton label="Sign out" icon={<GearIcon aria-hidden />} onClick={onClick} />);
    await user.tab();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("renders the three variants and two sizes", () => {
    render(
      <>
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost" size="small">
          Ghost
        </Button>
      </>,
    );
    expect(screen.getAllByRole("button")).toHaveLength(3);
  });
});

describe("Button press (FR-127)", () => {
  it("every variant carries the instant 1 px press offset and no transition", () => {
    render(
      <>
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <IconButton label="Icon" icon={<GearIcon aria-hidden />} />
      </>,
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(4);
    for (const button of buttons) {
      expect(button).toHaveClass("active:translate-y-px");
      expect(button.className).not.toMatch(/transition/);
    }
  });
});
