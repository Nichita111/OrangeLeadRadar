import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { Callout } from "./Callout";
describe("Callout", () => {
  it.each(["neutral", "accent", "caution", "error"] as const)(
    "FR-121 renders the %s kind with its icon",
    async (kind) => {
      const { container } = render(
        <Callout kind={kind} title="State">
          One sentence.
        </Callout>,
      );
      expect(screen.getByText("State").tagName).toBe("STRONG");
      expect(container.querySelector("svg")).toBeInTheDocument();
      expect(
        (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
      ).toEqual([]);
    },
  );
});
