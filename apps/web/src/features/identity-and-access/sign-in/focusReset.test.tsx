import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { errorEnvelope, errorResponse } from "../../../api/authenticationAndUsers.fixtures";
import { renderApp } from "../../../testRender";
import { http, server } from "../../../testServer";

let meCalls = 0;
function anonymous() {
  meCalls = 0;
  server.use(
    http.get("/api/v1/auth/me", async () => {
      meCalls += 1;
      // A real answer takes a moment, long enough for the screen to render the refetch.
      await new Promise((resolve) => setTimeout(resolve, 30));
      return errorResponse(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), 401);
    }),
  );
}

/** Hides the page and shows it again, as switching to another window and back does. */
async function switchWindowAndBack() {
  const setVisibility = (state: DocumentVisibilityState) => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
    document.dispatchEvent(new Event("visibilitychange", { bubbles: true }));
  };
  act(() => {
    setVisibility("hidden");
    setVisibility("visible");
  });
  // Outside act, so each state the refetch passes through renders, as in a browser.
  await new Promise((resolve) => setTimeout(resolve, 200));
}

afterEach(() => {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
});

describe("window focus keeps anonymous screens", () => {
  it("Sign in keeps what was typed", async () => {
    const user = userEvent.setup();
    anonymous();
    renderApp("/login");
    await user.type(await screen.findByLabelText("Email"), "sales@leadradar.local");
    const before = meCalls;
    await switchWindowAndBack();
    expect(meCalls).toBe(before);
    expect(screen.getByLabelText("Email")).toHaveValue("sales@leadradar.local");
  });

  it("Landing stays mounted", async () => {
    anonymous();
    renderApp("/");
    const heading = await screen.findByRole("heading", { level: 1 });
    await switchWindowAndBack();
    expect(screen.getByRole("heading", { level: 1 })).toBe(heading);
  });

  it("Accept invite keeps what was typed", async () => {
    const user = userEvent.setup();
    anonymous();
    server.use(
      http.post("/api/v1/auth/invite", ({ response }) =>
        response(200).json({
          email: "new@leadradar.local",
          role: "SALES",
          invited_by: "Olga Admin",
          created_at: "2026-09-27T10:00:00Z",
          expires_at: "2026-09-30T10:00:00Z",
          password_min_length: 12,
        }),
      ),
    );
    renderApp("/invite#a1b2");
    await user.type(await screen.findByLabelText("Display name"), "Ana");
    await switchWindowAndBack();
    expect(screen.getByLabelText("Display name")).toHaveValue("Ana");
  });
});
