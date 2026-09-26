import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Quote } from "./Quote";
import { ScoreNumber } from "./ScoreNumber";

describe("ScoreNumber (FR-112)", () => {
  it("shows Priority larger than Fit, in the mono face, with the meaning line", () => {
    render(
      <>
        <ScoreNumber label="Priority" value={78} size="large" />
        <ScoreNumber label="Fit" value={88} meaning="How well it matches" />
      </>,
    );
    const priority = screen.getByText("78");
    const fit = screen.getByText("88");
    expect(priority.className).toMatch(/\bnum\b/);
    expect(priority.className).toMatch(/text-title/);
    expect(fit.className).not.toMatch(/text-title/);
    expect(screen.getByText("How well it matches")).toBeInTheDocument();
    expect(screen.getByText("Priority")).toBeInTheDocument();
  });

  it("draws its bar without a track", () => {
    const { container } = render(<ScoreNumber label="Fit" value={50} meaning="x" />);
    expect(container.querySelectorAll("[data-bar]")).toHaveLength(1);
    expect(container.querySelector("[data-bar-track]")).toBeNull();
  });
});

describe("Quote (FR-116)", () => {
  it("shows the translation only when given, then source domain, label and age", () => {
    const { rerender } = render(
      <Quote
        text="DHL setzt KI-Agenten ein."
        sourceDomain="group.dhl.com"
        sourceLabel="Press release"
        at="2026-09-05T12:00:00Z"
        now={new Date("2026-09-26T12:00:00Z")}
      />,
    );
    expect(screen.getByText("DHL setzt KI-Agenten ein.")).toBeInTheDocument();
    expect(screen.queryByText(/English:/)).not.toBeInTheDocument();
    expect(screen.getByText(/group\.dhl\.com/)).toBeInTheDocument();
    expect(screen.getByText("3 weeks ago")).toBeInTheDocument();

    rerender(
      <Quote
        text="DHL setzt KI-Agenten ein."
        english="DHL uses AI agents."
        sourceDomain="group.dhl.com"
        sourceLabel="Press release"
        at="2026-09-05T12:00:00Z"
        now={new Date("2026-09-26T12:00:00Z")}
      />,
    );
    expect(screen.getByText(/DHL uses AI agents\./)).toBeInTheDocument();
  });
});
