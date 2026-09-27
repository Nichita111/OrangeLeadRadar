import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { anaSales, authenticatedUser, olgaAdmin } from "../api/authenticationAndUsers.fixtures";
import { ConfigProvider } from "../configContext";
import { testConfig } from "../testRender";
import { ConfidenceWord } from "./ConfidenceWord";
import { CurrentUserProvider } from "./CurrentUser";

describe("ConfidenceWord (FR-009, N-10)", () => {
  it("shows an Admin the word, and the number only in a tooltip that also opens on focus", async () => {
    const user = userEvent.setup();
    render(
      <ConfigProvider config={testConfig}>
        <CurrentUserProvider user={authenticatedUser(olgaAdmin)}>
          <ConfidenceWord value={0.9} />
        </CurrentUserProvider>
      </ConfigProvider>,
    );
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.queryByText(/0\.9/)).not.toBeInTheDocument();

    await user.tab();
    expect(screen.getByText("High")).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent("0.90");
  });

  it("never shows Sales the number, anywhere in the DOM, even after focus", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <ConfigProvider config={testConfig}>
        <CurrentUserProvider user={authenticatedUser(anaSales)}>
          <ConfidenceWord value={0.9} />
        </CurrentUserProvider>
      </ConfigProvider>,
    );
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/0\.9/);

    await user.tab();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/0\.9/);
  });
});
