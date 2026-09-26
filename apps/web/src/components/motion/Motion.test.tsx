import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { BlurInText } from "./BlurInText";
import { ShimmerLabel } from "./ShimmerLabel";

beforeEach(() =>
  vi.stubGlobal(
    "matchMedia",
    vi
      .fn()
      .mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  ),
);

describe("motion, FR-124 and FR-125", () => {
  it("shows Blur-in text at its end state under reduced motion", async () => {
    const { container } = render(<BlurInText>Nothing here yet</BlurInText>);
    expect(screen.getByText("Nothing here yet")).toHaveStyle({ opacity: "1", filter: "blur(0px)" });
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("shows a static mark and label under reduced motion", async () => {
    const { container } = render(<ShimmerLabel>Refreshing</ShimmerLabel>);
    expect(screen.getByText("Refreshing")).toBeVisible();
    expect(container.querySelector("svg")).not.toHaveClass("animate-spin");
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
