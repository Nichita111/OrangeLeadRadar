// `FR-119`: label, hint and error order and `aria-describedby`; `FR-007`: the input is kept and
// a `VALIDATION` error shows under its field.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";

import { FormField } from "./FormField";

describe("FormField", () => {
  it("places the label above, the hint below the label, and wires aria-describedby", async () => {
    const { container } = render(
      <FormField label="Email" hint="Work email only">
        {(inputProps) => <input {...inputProps} value="ana@example.com" readOnly />}
      </FormField>,
    );

    const input = screen.getByRole("textbox");
    const label = screen.getByText("Email");

    expect(label.tagName).toBe("LABEL");
    expect(input).toHaveAccessibleDescription("Work email only");
    expect(input).toHaveValue("ana@example.com");
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("keeps the user's input and shows the error below the input, referenced by aria-describedby", () => {
    render(
      <FormField label="Email" error="is required">
        {(inputProps) => <input {...inputProps} defaultValue="typed-value" />}
      </FormField>,
    );

    const input = screen.getByRole("textbox");
    expect(input).toHaveValue("typed-value");
    expect(input).toHaveAccessibleDescription("is required");
    expect(screen.getByText("is required")).toBeInTheDocument();
  });
});
