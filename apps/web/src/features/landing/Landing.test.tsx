import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { authenticatedUser, olgaAdmin } from "../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../api/contract";
import { anonymous, renderApp, signedInAs, testConfig } from "../../testRender";
import { http, server } from "../../testServer";
import { STEPS } from "./Landing";

describe("Landing (WF-27)", () => {
  it("FR-161, FR-165: shows the eight steps in order with their words, without WebGL", async () => {
    anonymous();
    renderApp("/");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Know which accounts to call, and why.",
      }),
    ).toBeInTheDocument();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(STEPS.slice(1).map((s) => s.title));
    expect(screen.getByText("Open the live demo as a Sales or an Admin user.")).toBeInTheDocument();
    const dots = within(screen.getByRole("navigation", { name: "Steps" })).getAllByRole("button");
    expect(dots.map((d) => d.getAttribute("aria-label"))).toEqual(STEPS.map((s) => s.name));
    expect(dots[0]).toHaveAttribute("aria-current", "step");
  });

  it("FR-106: Landing is dark in both schemes, and only while it is shown", async () => {
    anonymous();
    const { router } = renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    expect(document.documentElement.dataset["scheme"]).toBe("dark");
    await router.navigate("/login");
    await screen.findByLabelText("Email");
    expect(document.documentElement.dataset["scheme"]).toBeUndefined();
  });

  it("FR-162: the header and the last step each have a Sign in that opens Sign in", async () => {
    anonymous();
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    const links = screen.getAllByRole("link", { name: "Sign in" });
    expect(links).toHaveLength(2);
    links.forEach((link) => {
      expect(link).toHaveAttribute("href", "/login");
    });
    expect(screen.queryByRole("button", { name: "Enter as Sales" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enter as Admin" })).not.toBeInTheDocument();
  });

  it("FR-162: with DEMO_SIGN_IN, Enter as Admin signs in through API-78 and opens Prospects", async () => {
    const user = userEvent.setup();
    anonymous();
    const seen: Schemas["DemoLoginRequest"][] = [];
    server.use(
      http.post("/api/v1/auth/demo-login", async ({ request, response }) => {
        seen.push(await request.json());
        signedInAs(olgaAdmin);
        return response(200).json(authenticatedUser(olgaAdmin));
      }),
    );
    const { router } = renderApp("/", { ...testConfig, DEMO_SIGN_IN: true });
    await user.click(await screen.findByRole("button", { name: "Enter as Admin" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
    expect(seen).toEqual([{ role: "ADMIN" }]);
  });

  it("FR-163: a signed-in user opening / is sent to /prospects", async () => {
    signedInAs(olgaAdmin);
    const { router } = renderApp("/");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
  });
});
