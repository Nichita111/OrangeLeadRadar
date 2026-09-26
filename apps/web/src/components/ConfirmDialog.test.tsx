import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";

function Harness({ onConfirm }: { onConfirm: () => void }) {
  return (
    <ConfirmDialog
      trigger={<Button variant="secondary">Disable</Button>}
      title="Disable user"
      description="Olga will be signed out."
      confirmLabel="Disable user"
      onConfirm={onConfirm}
    />
  );
}

describe("ConfirmDialog (FR-015, FR-123)", () => {
  it("titles itself with the action and puts Cancel before the verb button", async () => {
    const user = userEvent.setup();
    render(<Harness onConfirm={() => undefined} />);
    await user.click(screen.getByRole("button", { name: "Disable" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Disable user" });
    expect(dialog).toHaveTextContent("Olga will be signed out.");
    const buttons = screen.getAllByRole("button").filter((b) => dialog.contains(b));
    expect(buttons.map((b) => b.textContent)).toEqual(["Cancel", "Disable user"]);
  });

  it("only the confirm button calls onConfirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    await user.click(screen.getByRole("button", { name: "Disable" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(onConfirm).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Disable" }));
    await user.click(await screen.findByRole("button", { name: "Disable user" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("Escape closes the dialog and focus returns to the opener", async () => {
    const user = userEvent.setup();
    render(<Harness onConfirm={() => undefined} />);
    const opener = screen.getByRole("button", { name: "Disable" });
    await user.click(opener);
    await screen.findByRole("alertdialog");
    await user.keyboard("{Escape}");
    await vi.waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(opener).toHaveFocus();
  });
});
