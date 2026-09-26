// `FR-106`, `FR-125`: the overlay uses a token colour and, under reduced motion, the dialog
// renders at its motion end state (no animated opacity). Kept in its own file: `motion`'s reduced-
// motion detection reads `matchMedia` once per module instance and caches the result, so the
// stub below must be in place before this file's first render.
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { ConfirmDialog } from "./ConfirmDialog";

vi.stubGlobal(
  "matchMedia",
  vi.fn().mockReturnValue({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }),
);

it("FR-106 FR-125 uses a token overlay and the motion end state when motion is reduced", async () => {
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
  expect(
    (await axe(document.body, { rules: { "color-contrast": { enabled: false } } })).violations,
  ).toEqual([]);
});
