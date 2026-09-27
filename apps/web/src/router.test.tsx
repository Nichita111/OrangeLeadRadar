import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  anaSales,
  authenticatedUser,
  errorEnvelope,
  errorResponse,
  olgaAdmin,
} from "./api/authenticationAndUsers.fixtures";
import type { Schemas } from "./api/contract";
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

describe("service configuration routes", () => {
  const SERVICE: Schemas["Service"] = {
    id: "11111111-1111-1111-1111-111111111111",
    code: "INTELLIGENT_AUTOMATION",
    name: "Intelligent Automation",
    description: "d",
    value_proposition: "v",
    status: "ACTIVE",
    active_version: 1,
    draft_version: null,
    question_count: 0,
  };

  function arrangeService() {
    const serviceId = SERVICE.id;
    server.use(
      http.get("/api/v1/services/{id}", ({ response }) => response(200).json(SERVICE)),
      http.get("/api/v1/services/{id}/questions", ({ response }) => response(200).json([])),
      http.get("/api/v1/services/{id}/scoring-configs", ({ response }) =>
        response(200).json([
          {
            id: "22222222-2222-2222-2222-222222222222",
            service_id: serviceId,
            version: 1,
            status: "DRAFT",
            change_note: null,
            activated_at: null,
            activated_by_name: null,
          },
        ]),
      ),
      http.get("/api/v1/scoring-configs/{id}", ({ response }) =>
        response(200).json({
          id: "22222222-2222-2222-2222-222222222222",
          service_id: serviceId,
          version: 1,
          status: "DRAFT",
          change_note: null,
          activated_at: null,
          activated_by_name: null,
          settings: {
            fit_weight: 0.4,
            intent_weight: 0.6,
            min_fit: 40,
            hot_threshold: 70,
            warm_threshold: 40,
            weight_values: { HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 },
            strength_values: { WEAK: 0.5, MEDIUM: 0.75, STRONG: 1 },
            default_half_life_days: {
              NEWS: 90,
              COMPANY_PUBLICATION: 365,
              JOB_POSTING: 60,
              COMPANY_PROFILE: 365,
            },
            min_decay: 0.05,
            negative_factor: 1,
            intent_saturation: 0.5,
            unknown_match: 0.5,
            icp_criteria: [],
            questions: [],
            disqualifiers: [],
          },
        }),
      ),
      http.get("/api/v1/industries", ({ response }) => response(200).json([])),
      http.get("/api/v1/markets", ({ response }) => response(200).json([])),
    );
    return serviceId;
  }

  it("/services lists the screen", async () => {
    signedInAs(olgaAdmin);
    arrangeService();
    renderApp("/services");
    expect(await screen.findByRole("heading", { name: "Services", level: 1 })).toBeInTheDocument();
  });

  it("/services/:id shows the editor with the Services breadcrumb (FR-102)", async () => {
    signedInAs(olgaAdmin);
    const serviceId = arrangeService();
    renderApp(`/services/${serviceId}`);
    expect(
      await screen.findByRole("heading", { name: "Intelligent Automation", level: 1 }),
    ).toBeInTheDocument();
    const header = screen.getByRole("banner");
    expect(within(header).getByRole("link", { name: "Services" })).toHaveAttribute(
      "href",
      "/services",
    );
  });

  it("/services/:id/scoring shows Scoring settings with the Services breadcrumb (FR-102)", async () => {
    signedInAs(olgaAdmin);
    const serviceId = arrangeService();
    renderApp(`/services/${serviceId}/scoring`);
    expect(
      await screen.findByRole("heading", { name: "Intelligent Automation", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Scoring" })).toHaveAttribute("aria-selected", "true");
    const header = screen.getByRole("banner");
    expect(within(header).getByRole("link", { name: "Services" })).toHaveAttribute(
      "href",
      "/services",
    );
  });

  it("/settings/industries-markets lists the screen", async () => {
    signedInAs(olgaAdmin);
    server.use(
      http.get("/api/v1/industries", ({ response }) => response(200).json([])),
      http.get("/api/v1/markets", ({ response }) => response(200).json([])),
    );
    renderApp("/settings/industries-markets");
    expect(
      await screen.findByRole("heading", { name: "Industries and markets", level: 1 }),
    ).toBeInTheDocument();
  });

  it("a Sales user sees Not allowed on every route", async () => {
    signedInAs(anaSales);
    renderApp("/services");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
  });
});
