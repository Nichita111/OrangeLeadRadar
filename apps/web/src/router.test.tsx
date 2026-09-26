import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
  errorResponse,
  olgaAdmin,
} from "./api/authenticationAndUsers.fixtures";
import { anonymous, renderApp, signedInAs } from "./testRender";
import { http, server } from "./testServer";

describe("routes and guards (FR-006, FR-159, DC-3, DC-4)", () => {
  it("an anonymous visit to /users goes to Sign in with the return path", async () => {
    anonymous();
    const { router } = renderApp("/users");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("?return=%2Fusers");
  });

  it("Sales on /users sees Not allowed naming Admin, and the users are never requested", async () => {
    signedInAs(anaSales);
    let requested = 0;
    server.use(
      http.get("/api/v1/users", ({ response }) => {
        requested += 1;
        return response(200).json([]);
      }),
    );
    renderApp("/users");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
    expect(screen.getByText("This page needs the Admin role.")).toBeInTheDocument();
    expect(requested).toBe(0);
  });

  it("/ goes to /prospects", async () => {
    signedInAs(anaSales);
    const { router } = renderApp("/");
    expect(await screen.findByRole("heading", { name: "Prospects" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/prospects");
  });

  it("an unknown route shows Not found inside the shell", async () => {
    signedInAs(anaSales);
    renderApp("/nope");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByText("This page does not exist.")).toBeInTheDocument();
    expect(document.title).toBe("Page not found · LeadRadar");
    expect(document.body).not.toHaveTextContent(/p_positive|escalation|triage/i);
  });

  it("FR-016: Not found and Not allowed work by keyboard, the link goes to Prospects", async () => {
    const user = userEvent.setup();
    signedInAs(anaSales);
    const { router } = renderApp("/users");
    const link = await screen.findByRole("link", { name: "Back to Prospects" });
    expect(document.body).not.toHaveTextContent(/p_positive|escalation|triage/i);
    link.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
    await router.navigate("/nope");
    const notFoundLink = await screen.findByRole("link", { name: "Go to Prospects" });
    notFoundLink.focus();
    expect(notFoundLink).toHaveFocus();
  });

  it("a 401 from API-04 goes to /login?return=%2Fusers and the cache is cleared", async () => {
    let expired = false;
    let meCalls = 0;
    server.use(
      http.get("/api/v1/auth/me", ({ response }) => {
        meCalls += 1;
        return expired
          ? errorResponse(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), 401)
          : response(200).json(authenticatedUser(olgaAdmin));
      }),
      http.get("/api/v1/users", () => {
        expired = true;
        return errorResponse(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), 401);
      }),
    );
    const { router } = renderApp("/users");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/login");
    });
    expect(router.state.location.search).toBe("?return=%2Fusers");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(meCalls).toBeGreaterThanOrEqual(2);
  });

  it("a 403 from a guarded call renders Not allowed naming Admin", async () => {
    signedInAs(olgaAdmin);
    server.use(
      http.get("/api/v1/users", () =>
        errorResponse(errorEnvelope("FORBIDDEN", "The role does not allow it."), 403),
      ),
    );
    renderApp("/users");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
    expect(screen.getByText("This page needs the Admin role.")).toBeInTheDocument();
  });

  it("any other error of the session check renders the error state with Retry", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        errorResponse(errorEnvelope("INTERNAL", "Something went wrong on our side."), 500),
      ),
    );
    renderApp("/users");
    expect(await screen.findByText("Something went wrong on our side.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
