import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { anaSales, errorEnvelope, olgaAdmin } from "../api/authenticationAndUsers.fixtures";
import { anonymous, renderApp, signedInAs } from "../testRender";
import { http, server } from "../testServer";

const WORK = ["Prospects", "Alerts", "Accounts", "Suggested accounts", "Runs", "Labelling"];
const ADMIN = [
  "Services",
  "Industries and markets",
  "Quality",
  "Source plug-ins",
  "Users",
  "Audit log",
];

describe("navigation (FR-001, FR-101)", () => {
  it("for Sales shows the six Work entries and no Admin only group", async () => {
    signedInAs(anaSales);
    renderApp("/nope");
    const nav = await screen.findByRole("navigation");
    const labels = within(nav)
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(labels).toEqual(WORK);
    expect(within(nav).getByText("Work")).toBeInTheDocument();
    expect(within(nav).queryByText("Admin only")).not.toBeInTheDocument();
  });

  it("for Admin shows both groups, each entry with its icon and label", async () => {
    signedInAs(olgaAdmin);
    renderApp("/nope");
    const nav = await screen.findByRole("navigation");
    expect(
      within(nav)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual([...WORK, ...ADMIN]);
    expect(within(nav).getByText("Admin only")).toBeInTheDocument();
    for (const link of within(nav).getAllByRole("link")) {
      expect(link.querySelector("svg[data-icon]")).not.toBeNull();
    }
    expect(within(nav).getByRole("link", { name: "Users" })).toHaveAttribute("href", "/users");
  });
});

describe("header (FR-102)", () => {
  it("shows the breadcrumb and the Admin only chip on /users, and marks the current entry", async () => {
    signedInAs(olgaAdmin);
    server.use(http.get("/api/v1/users", ({ response }) => response(200).json([olgaAdmin])));
    renderApp("/users");
    const header = await screen.findByRole("banner");
    expect(within(header).getByText("Users")).toBeInTheDocument();
    expect(within(header).getByText("Admin only")).toBeInTheDocument();
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Users" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Runs" })).not.toHaveAttribute("aria-current");
    expect(document.title).toBe("Users · LeadRadar");
  });
});

describe("user card (FR-004)", () => {
  it("shows the display name and role", async () => {
    signedInAs(anaSales);
    renderApp("/nope");
    const card = await screen.findByRole("region", { name: "Signed in user" });
    expect(within(card).getByText("Ana Sales")).toBeInTheDocument();
    expect(within(card).getByText("Sales")).toBeInTheDocument();
  });

  it("Sign out calls API-02, clears the cache and lands on Sign in", async () => {
    const user = userEvent.setup();
    let signedIn = true;
    server.use(
      http.get("/api/v1/auth/me", ({ response }) =>
        signedIn
          ? response(200).json({
              id: anaSales.id,
              email: anaSales.email,
              display_name: anaSales.display_name,
              role: anaSales.role,
            })
          : response("default").json(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), {
              status: 401,
            }),
      ),
      http.post("/api/v1/auth/logout", ({ request, response }) => {
        expect(request.headers.get("X-Requested-With")).toBe("XMLHttpRequest");
        signedIn = false;
        return response(204).empty();
      }),
    );
    const { router } = renderApp("/nope");
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("a failed sign-out (FR-120) shows the message and the user stays signed in", async () => {
    const user = userEvent.setup();
    signedInAs(anaSales);
    server.use(
      http.post("/api/v1/auth/logout", ({ response }) =>
        response("default").json(errorEnvelope("INTERNAL", "Sign-out failed. Try again."), {
          status: 500,
        }),
      ),
    );
    const { router } = renderApp("/nope");
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByText("Sign-out failed. Try again.")).toBeInTheDocument();
    // FR-120: a failure is a callout, never a toast.
    expect(
      screen
        .queryAllByRole("status")
        .some((element) => element.textContent.includes("Sign-out failed")),
    ).toBe(false);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/nope");
    });
    expect(screen.getByText("Ana Sales")).toBeInTheDocument();
  });

  it("a 401 on sign-out lands on Sign in as well", async () => {
    const user = userEvent.setup();
    signedInAs(anaSales);
    server.use(
      http.post("/api/v1/auth/logout", ({ response }) => {
        anonymous();
        return response("default").json(errorEnvelope("UNAUTHENTICATED", "Sign in to continue."), {
          status: 401,
        });
      }),
    );
    renderApp("/nope");
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
