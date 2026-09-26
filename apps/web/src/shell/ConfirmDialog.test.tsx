// `FR-015`, `FR-123`: Cancel comes before the confirm verb; Escape closes; focus returns to the
// opener. The reduced-motion overlay/motion-end-state case lives in
// `ConfirmDialog.reducedMotion.test.tsx`: `motion`'s reduced-motion detection reads and caches
// `matchMedia` once per module instance, so it needs a file of its own where that cache starts
// fresh, ahead of the plain-render tests below which never stub `matchMedia`.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
});
