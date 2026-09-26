import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
} from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { setReducedMotion } from "../../../testEnvironment";
import { anonymous, renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

function arrangeLogin(
  respond: (
    body: Schemas["LoginRequest"],
    respondWith: Parameters<Parameters<typeof http.post<"/api/v1/auth/login">>[1]>[0]["response"],
  ) => Response,
): Schemas["LoginRequest"][] {
  const seen: Schemas["LoginRequest"][] = [];
  server.use(
    http.post("/api/v1/auth/login", async ({ request, response }) => {
      const body = await request.json();
      seen.push(body);
      return respond(body, response);
    }),
  );
  return seen;
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Email"), "sales@leadradar.local");
  await user.type(screen.getByLabelText("Password"), "correct horse");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("Sign in layout (FR-160, FR-152)", () => {
  it("has the brand panel with the headline and the form panel with title, lead and hints", async () => {
    setReducedMotion(true);
    anonymous();
    renderApp("/login");
    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByText("LeadRadar")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Know which accounts to call, and exactly why." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(
      screen.getByText("Use the email and password your Admin created for you."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAccessibleDescription(
      "The address your Admin created for you.",
    );
    expect(screen.getByLabelText("Password")).toHaveAccessibleDescription(
      "Several failed attempts in a row lock the account for a short time.",
    );
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    expect(document.title).toBe("Sign in · LeadRadar");
  });
});

describe("Sign in session check (FR-093)", () => {
  it("a signed-in visitor goes to /prospects", async () => {
    signedInAs(anaSales);
    const { router } = renderApp("/login");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
  });

  it("any other error of the check shows the error state", async () => {
    server.use(
      http.get("/api/v1/auth/me", ({ response }) =>
        response("default").json(errorEnvelope("INTERNAL", "Something went wrong on our side."), {
          status: 500,
        }),
      ),
    );
    renderApp("/login");
    expect(await screen.findByText("Something went wrong on our side.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("Sign in submit (FR-093, FR-094, FR-007)", () => {
  it("sends email and password, and success goes to /prospects", async () => {
    const user = userEvent.setup();
    anonymous();
    const seen = arrangeLogin((_body, response) => response(200).json(authenticatedUser(anaSales)));
    const { router } = renderApp("/login");
    await screen.findByLabelText("Email");
    signedInAs(anaSales);
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
    expect(seen).toEqual([{ email: "sales@leadradar.local", password: "correct horse" }]);
  });

  it("success goes to the return path when it is a path of this client", async () => {
    const user = userEvent.setup();
    anonymous();
    arrangeLogin((_body, response) => response(200).json(authenticatedUser(anaSales)));
    const { router } = renderApp("/login?return=%2Fusers");
    await screen.findByLabelText("Email");
    signedInAs(anaSales);
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/users");
    });
  });

  it("success ignores a return path that leaves this client", async () => {
    const user = userEvent.setup();
    anonymous();
    arrangeLogin((_body, response) => response(200).json(authenticatedUser(anaSales)));
    const { router } = renderApp("/login?return=%2F%2Fevil.example");
    await screen.findByLabelText("Email");
    signedInAs(anaSales);
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
  });

  it.each([
    [401, "UNAUTHENTICATED", "The email or password is wrong."],
    [423, "LOCKED", "Too many failed attempts. Try again in 15 minutes."],
    [403, "FORBIDDEN", "This account is disabled."],
  ] as const)(
    "a %d shows the api's message above the button and keeps the input",
    async (status, code, message) => {
      const user = userEvent.setup();
      anonymous();
      arrangeLogin((_body, response) =>
        response("default").json(errorEnvelope(code, message), { status }),
      );
      const { router } = renderApp("/login");
      await fillAndSubmit(user);
      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(screen.getByLabelText("Email")).toHaveValue("sales@leadradar.local");
      expect(screen.getByLabelText("Password")).toHaveValue("correct horse");
      expect(router.state.location.pathname).toBe("/login");
    },
  );

  it("a VALIDATION error shows beside its field", async () => {
    const user = userEvent.setup();
    anonymous();
    arrangeLogin((_body, response) =>
      response("default").json(
        errorEnvelope("VALIDATION", "The input is invalid.", {
          fields: [{ field: "email", message: "Enter a valid email address." }],
        }),
        { status: 422 },
      ),
    );
    renderApp("/login");
    await fillAndSubmit(user);
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAccessibleDescription(
      "The address your Admin created for you. Enter a valid email address.",
    );
    expect(screen.getByLabelText("Email")).toHaveValue("sales@leadradar.local");
  });

  it("FR-016: works entirely by keyboard, Enter submits", async () => {
    const user = userEvent.setup();
    anonymous();
    const seen = arrangeLogin((_body, response) => response(200).json(authenticatedUser(anaSales)));
    renderApp("/login");
    await screen.findByLabelText("Email");
    await user.tab();
    expect(screen.getByLabelText("Email")).toHaveFocus();
    await user.keyboard("sales@leadradar.local");
    await user.tab();
    expect(screen.getByLabelText("Password")).toHaveFocus();
    await user.keyboard("correct horse{Enter}");
    await waitFor(() => {
      expect(seen).toHaveLength(1);
    });
  });

  it("FR-008: shows no internal names", async () => {
    anonymous();
    renderApp("/login");
    await screen.findByLabelText("Email");
    expect(document.body).not.toHaveTextContent(/p_positive|escalation|triage/i);
  });
});
