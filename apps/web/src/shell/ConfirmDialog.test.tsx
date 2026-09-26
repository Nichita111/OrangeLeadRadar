// `FR-015`, `FR-123`: Cancel comes before the confirm verb; Escape closes; focus returns to the
// opener.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("places Cancel before the confirm verb, and Escape returns focus to the opener", async () => {
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        trigger={<button>Disable user</button>}
        title="Disable Ana Sales?"
        description="She keeps her history; she can no longer sign in."
        confirmLabel="Disable user"
        onConfirm={() => {
          /* not exercised here */
        }}
      />,
    );

    const opener = screen.getByRole("button", { name: "Disable user" });
    await user.click(opener);

    const buttons = await screen.findAllByRole("button", { name: /cancel|disable user/i });
    expect(buttons.map((button) => button.textContent)).toEqual(["Cancel", "Disable user"]);

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(opener).toHaveFocus();
  });

  it("calls onConfirm when the confirming button is pressed", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        trigger={<button>Erase contact</button>}
        title="Erase this contact?"
        description="This cannot be undone."
        confirmLabel="Erase contact"
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Erase contact" }));
    const confirmButtons = await screen.findAllByRole("button", { name: "Erase contact" });
    const confirmButton = confirmButtons.at(-1);
    expect(confirmButton).toBeDefined();
    if (confirmButton !== undefined) await user.click(confirmButton);

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("FR-106 FR-125 uses a token overlay and the motion end state when motion is reduced", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
    const { container } = render(
      <ConfirmDialog
        open
        title="Disable user?"
        description="The user keeps their history and can no longer sign in."
        confirmLabel="Disable user"
        onConfirm={vi.fn()}
      />,
    );
    const overlay = container.ownerDocument.querySelector("[data-state='open'][data-overlay]");
    expect(overlay).toHaveClass("bg-text/40");
    expect(overlay).toHaveStyle({ opacity: "1" });
    expect(screen.getByRole("alertdialog")).toHaveStyle({ opacity: "1" });
    expect((await axe(document.body, { rules: { "color-contrast": { enabled: false } } })).violations).toEqual([]);
    vi.unstubAllGlobals();
  });
});
