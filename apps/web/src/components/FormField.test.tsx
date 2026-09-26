import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Input } from "./controls";
import { FormField } from "./FormField";

describe("FormField (FR-119)", () => {
  it("places the label above and associated, and links hint and error with aria-describedby", () => {
    render(
      <FormField
        label="Email"
        hint="The address your Admin created for you."
        error="Enter an email."
      >
        {(field) => <Input {...field} type="email" />}
      </FormField>,
    );
    const input = screen.getByLabelText("Email");
    const label = screen.getByText("Email");
    const hint = screen.getByText("The address your Admin created for you.");
    const error = screen.getByText("Enter an email.");
    expect(input).toHaveAccessibleDescription(
      "The address your Admin created for you. Enter an email.",
    );
    expect(input).toBeInvalid();
    expect(label.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(input.compareDocumentPosition(error) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(input.compareDocumentPosition(hint) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("is valid and undescribed without a hint or error", () => {
    render(<FormField label="Name">{(field) => <Input {...field} />}</FormField>);
    expect(screen.getByLabelText("Name")).toBeValid();
    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-describedby");
  });
});
