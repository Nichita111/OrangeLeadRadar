import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { setReducedMotion } from "../../testEnvironment";
import { Aurora } from "./Aurora";
import { BlurText } from "./BlurText";

describe("BlurText (FR-125)", () => {
  it("under reduced motion shows its end state at once", () => {
    setReducedMotion(true);
    render(<BlurText text="Know which accounts to call" />);
    const words = screen.getAllByText(/^(Know|which|accounts|to|call)$/);
    expect(words).toHaveLength(5);
    for (const word of words) {
      expect(word).toHaveStyle({ opacity: "1" });
    }
  });

  it("keeps the whole sentence readable by assistive technology", () => {
    render(<BlurText text="Know which accounts to call" />);
    expect(
      screen.getByRole("heading", { name: "Know which accounts to call" }),
    ).toBeInTheDocument();
  });
});

describe("Aurora (FR-125, FR-128)", () => {
  it("under reduced motion shows the still gradient and loads no WebGL", () => {
    setReducedMotion(true);
    render(<Aurora />);
    expect(screen.getByTestId("aurora-still")).toBeInTheDocument();
    expect(screen.queryByTestId("aurora-canvas")).not.toBeInTheDocument();
  });

  it("a failed load leaves the still gradient", async () => {
    render(<Aurora load={() => Promise.reject(new Error("no webgl"))} />);
    expect(await screen.findByTestId("aurora-still")).toBeInTheDocument();
    expect(screen.queryByTestId("aurora-canvas")).not.toBeInTheDocument();
  });
});
