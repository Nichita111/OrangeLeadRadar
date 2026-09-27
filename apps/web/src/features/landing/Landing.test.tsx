import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { olgaAdmin } from "../../api/authenticationAndUsers.fixtures";
import { anonymous, renderApp, signedInAs } from "../../testRender";
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
    expect(screen.getByText("Sign in with the account your Admin created.")).toBeInTheDocument();
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

  it("FR-162: the header and the last step each have a Sign in that opens Sign in, and nothing else signs in", async () => {
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

  it("FR-163: a signed-in user opening / is sent to /prospects", async () => {
    signedInAs(olgaAdmin);
    const { router } = renderApp("/");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/prospects");
    });
  });
});
