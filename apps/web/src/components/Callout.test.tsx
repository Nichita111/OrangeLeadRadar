import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Callout, type CalloutKind } from "./Callout";
import { ToastProvider, useToast } from "./Toast";
import { TOAST_VISIBLE_MS } from "./motion/values";

describe("Callout (FR-121)", () => {
  it("carries one icon per kind, each its own", () => {
    const kinds: CalloutKind[] = ["neutral", "accent", "caution", "error"];
    const icons = kinds.map((kind) => {
      const { container, unmount } = render(<Callout kind={kind}>Something happened.</Callout>);
      const svg = container.querySelector("svg")?.outerHTML;
      unmount();
      return svg;
    });
    expect(icons.every((svg) => svg !== undefined)).toBe(true);
    expect(new Set(icons).size).toBe(4);
  });

  it("puts the first sentence in bold when it names the state", () => {
    render(
      <Callout kind="caution" lead="Locked.">
        Try again in 5 minutes.
      </Callout>,
    );
    expect(screen.getByText("Locked.").tagName).toBe("STRONG");
  });
});

function Opener({ message }: { message: string }) {
  const { notify } = useToast();
  return (
    <button
      type="button"
      onClick={() => {
        notify(message);
      }}
    >
      go
    </button>
  );
}

describe("Toast (FR-120)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("is announced as a status, can be dismissed", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Opener message="User created" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "go" }));
    await vi.waitFor(() => {
      const toast = screen
        .getAllByRole("status")
        .find((element) => element.textContent.includes("User created"));
      expect(toast).toBeDefined();
    });
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(screen.queryByText("User created")).not.toBeInTheDocument();
    });
  });

  it("leaves by itself after the Motion toast time", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(
      <ToastProvider>
        <Opener message="User updated" />
      </ToastProvider>,
    );
    await act(async () => {
      screen.getByRole("button", { name: "go" }).click();
      await Promise.resolve();
    });
    expect(screen.getByText("User updated")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(TOAST_VISIBLE_MS + 500);
    });
    expect(screen.queryByText("User updated")).not.toBeInTheDocument();
  });
});
