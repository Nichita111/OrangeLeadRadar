import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ConfigProvider } from "../configContext";
import { testConfig } from "../testRender";
import { ConfidenceWord } from "./ConfidenceWord";

describe("ConfidenceWord (FR-009)", () => {
  it("shows the word, and the number only in a tooltip", async () => {
    const user = userEvent.setup();
    render(
      <ConfigProvider config={testConfig}>
        <ConfidenceWord value={0.9} />
      </ConfigProvider>,
    );
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.queryByText(/0\.9/)).not.toBeInTheDocument();
    await user.hover(screen.getByText("High"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("0.90");
  });
});
