import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { notifyDone } from "./notifyDone";
import { Toaster } from "./Toaster";

beforeEach(() => {
  vi.stubGlobal(
    "matchMedia",
    vi
      .fn()
      .mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  );
});

it("FR-120 announces a completed action and lets the user dismiss it", async () => {
  const user = userEvent.setup();
  const { container } = render(<Toaster />);
  notifyDone("Service saved");
  expect(await screen.findByText("Service saved")).toBeVisible();
  expect(screen.getByRole("status")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Close toast" }));
  await waitFor(() => {
    expect(screen.queryByText("Service saved")).not.toBeInTheDocument();
  });
  expect(
    (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
  ).toEqual([]);
});
