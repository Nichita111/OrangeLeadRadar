import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
  errorResponse,
} from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { setReducedMotion } from "../../../testEnvironment";
import { anonymous, renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const TOKEN = "a1b2c3";

const preview: Schemas["InvitePreview"] = {
  email: "sales@leadradar.local",
  role: "SALES",
  invited_by: "Olga Admin",
  created_at: "2026-09-27T10:00:00Z",
  expires_at: "2026-09-30T10:00:00Z",
  password_min_length: 12,
};

/** Arranges `API-81` and returns the tokens it was sent. */
function arrangePreview(answer: "ok" | "gone" = "ok"): string[] {
  const tokens: string[] = [];
  server.use(
    http.post("/api/v1/auth/invite", async ({ request, response }) => {
      tokens.push((await request.json()).token);
      return answer === "ok"
        ? response(200).json(preview)
        : errorResponse(errorEnvelope("NOT_FOUND", "The invite does not exist."), 404);
    }),
  );
  return tokens;
}

describe("Accept invite (WF-28)", () => {
  it("FR-169, FR-170: previews the fragment's token in the body and shows the invitation", async () => {
    setReducedMotion(true);
    anonymous();
    const tokens = arrangePreview();
    renderApp(`/invite#${TOKEN}`);

    expect(await screen.findByRole("heading", { name: "You're invited." })).toBeInTheDocument();
    expect(
      screen.getByLabelText("Olga Admin invited you to LeadRadar as Sales"),
    ).toBeInTheDocument();
    expect(screen.getByText(/sales@leadradar\.local,/)).toBeInTheDocument();
    expect(tokens).toEqual([TOKEN]);
  });

  it("FR-169: a link that no longer works says so, with no form", async () => {
    anonymous();
    arrangePreview("gone");
    renderApp(`/invite#${TOKEN}`);

    expect(
      await screen.findByRole("heading", { name: "This invite link no longer works." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Ask your Admin for a new one.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  it("FR-169: a link without a token says it no longer works, without calling the api", async () => {
    anonymous();
    const tokens = arrangePreview();
    renderApp("/invite");
    expect(
      await screen.findByRole("heading", { name: "This invite link no longer works." }),
    ).toBeInTheDocument();
    expect(tokens).toEqual([]);
  });

  it("FR-171, FR-172: the column counts the password to the minimum; joining opens Prospects", async () => {
    const user = userEvent.setup();
    setReducedMotion(true);
    anonymous();
    arrangePreview();
    const sent: Schemas["InviteAccept"][] = [];
    server.use(
      http.post("/api/v1/auth/invite/accept", async ({ request, response }) => {
        sent.push(await request.json());
        signedInAs(anaSales);
        return response(200).json(authenticatedUser(anaSales));
      }),
    );
    const { router } = renderApp(`/invite#${TOKEN}`);

    await user.type(await screen.findByLabelText("Display name"), "Ana Sales");
    expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(
      "At least 12 characters.",
    );
    await user.type(screen.getByLabelText("Password"), "short");
    expect(screen.getByText("5/12")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Password"), "-but-long-now");
    expect(screen.getByText("12/12")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Join LeadRadar" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
    expect(sent).toEqual([
      { token: TOKEN, display_name: "Ana Sales", password: "short-but-long-now" },
    ]);
  });

  it("FR-171: a field error from the api shows beside its field", async () => {
    const user = userEvent.setup();
    anonymous();
    arrangePreview();
    server.use(
      http.post("/api/v1/auth/invite/accept", () =>
        errorResponse(
          errorEnvelope("VALIDATION", "The input is invalid.", {
            fields: [{ field: "password", message: "String should have at least 12 characters" }],
          }),
          422,
        ),
      ),
    );
    renderApp(`/invite#${TOKEN}`);
    await user.type(await screen.findByLabelText("Display name"), "Ana");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Join LeadRadar" }));
    expect(
      await screen.findByText("String should have at least 12 characters"),
    ).toBeInTheDocument();
  });

  it("FR-173: a signed-in user opening an invite is sent to Prospects", async () => {
    signedInAs(anaSales);
    arrangePreview();
    const { router } = renderApp(`/invite#${TOKEN}`);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
  });

  it("FR-106: the page is dark in both schemes", async () => {
    anonymous();
    arrangePreview();
    renderApp(`/invite#${TOKEN}`);
    await screen.findByRole("heading", { name: "You're invited." });
    expect(document.documentElement.dataset["scheme"]).toBe("dark");
  });
});
