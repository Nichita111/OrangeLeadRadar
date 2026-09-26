import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RelativeTime } from "./RelativeTime";

describe("RelativeTime (FR-010)", () => {
  it("renders a time element with the relative text and the absolute time in a tooltip", async () => {
    const user = userEvent.setup();
    render(<RelativeTime at="2026-09-26T10:00:00Z" now={new Date("2026-09-26T12:00:00Z")} />);
    const time = screen.getByText("2 hours ago");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("datetime", "2026-09-26T10:00:00Z");
    await user.hover(time);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("2026");
  });
});
