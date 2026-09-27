import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const automation: Schemas["Service"] = {
  id: "11111111-1111-1111-1111-111111111111",
  code: "INTELLIGENT_AUTOMATION",
  name: "Intelligent Automation",
  description: "Finds companies automating processes.",
  value_proposition: "Cuts manual work.",
  status: "ACTIVE",
  active_version: 3,
  draft_version: 4,
  question_count: 9,
};
const legacy: Schemas["Service"] = {
  id: "22222222-2222-2222-2222-222222222222",
  code: "LEGACY_MIGRATION",
  name: "Legacy Migration",
  description: "Finds companies migrating legacy systems.",
  value_proposition: "Speeds up migration.",
  status: "INACTIVE",
  active_version: 1,
  draft_version: null,
  question_count: 3,
};

function arrangeServices(initial: Schemas["Service"][]): Schemas["Service"][] {
  const services = [...initial];
  server.use(http.get("/api/v1/services", ({ response }) => response(200).json(services)));
  return services;
}

async function openServices() {
  signedInAs(olgaAdmin);
  const view = renderApp("/services");
  await screen.findByRole("heading", { name: "Services", level: 1 });
  return view;
}

describe("ServicesScreen (FR-018, FR-149)", () => {
  it("lists each service with description, status, scoring chips, questions and links", async () => {
    arrangeServices([automation, legacy]);
    await openServices();
    const row = await screen.findByRole("row", { name: /Intelligent Automation/ });
    expect(within(row).getByText("Finds companies automating processes.")).toBeInTheDocument();
    expect(within(row).getByText("INTELLIGENT_AUTOMATION")).toBeInTheDocument();
    expect(within(row).getByText("Active")).toBeInTheDocument();
    expect(within(row).getByText("v3")).toBeInTheDocument();
    expect(within(row).getByText("draft v4")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Intelligent Automation" })).toHaveAttribute(
      "href",
      "/services/11111111-1111-1111-1111-111111111111",
    );
    expect(within(row).getByRole("link", { name: "9 questions" })).toHaveAttribute(
      "href",
      "/services/11111111-1111-1111-1111-111111111111?tab=questions",
    );
    expect(within(row).getByRole("link", { name: "Scoring" })).toHaveAttribute(
      "href",
      "/services/11111111-1111-1111-1111-111111111111/scoring",
    );
    const legacyRow = await screen.findByRole("row", { name: /Legacy Migration/ });
    expect(within(legacyRow).getByText("Inactive")).toBeInTheDocument();
    expect(within(legacyRow).queryByText(/draft/)).not.toBeInTheDocument();
  });

  it("shows the empty sentence with New service", async () => {
    arrangeServices([]);
    await openServices();
    expect(
      await screen.findByText("No services yet. New service creates the first one."),
    ).toBeInTheDocument();
  });
});

describe("New service (FR-019)", () => {
  it("upper-snakes the code as typed and sends ServiceCreate", async () => {
    const user = userEvent.setup();
    const services = arrangeServices([]);
    const bodies: Schemas["ServiceCreate"][] = [];
    server.use(
      http.post("/api/v1/services", async ({ request, response }) => {
        const body = await request.json();
        bodies.push(body);
        const created: Schemas["Service"] = {
          id: automation.id,
          ...body,
          status: "ACTIVE",
          active_version: null,
          draft_version: 1,
          question_count: 0,
        };
        services.push(created);
        return response(200).json(created);
      }),
    );
    await openServices();
    await user.click(await screen.findByRole("button", { name: "New service" }));
    const dialog = await screen.findByRole("dialog", { name: "New service" });
    await user.type(within(dialog).getByLabelText("Code"), "new service");
    await user.type(within(dialog).getByLabelText("Name"), "New Service");
    await user.type(within(dialog).getByLabelText("Description"), "A description.");
    await user.type(within(dialog).getByLabelText("Value proposition"), "A proposition.");
    await user.click(within(dialog).getByRole("button", { name: "Create service" }));
    await waitFor(() => {
      expect(bodies).toEqual([
        {
          code: "NEW_SERVICE",
          name: "New Service",
          description: "A description.",
          value_proposition: "A proposition.",
        },
      ]);
    });
    expect(await screen.findByRole("row", { name: /New Service/ })).toBeInTheDocument();
  });

  it("a 409 shows as a callout with the input kept", async () => {
    const user = userEvent.setup();
    arrangeServices([automation]);
    server.use(
      http.post("/api/v1/services", () =>
        Response.json(
          { error: { code: "CONFLICT", message: "A service with that code already exists." } },
          { status: 409 },
        ),
      ),
    );
    await openServices();
    await user.click(await screen.findByRole("button", { name: "New service" }));
    const dialog = await screen.findByRole("dialog", { name: "New service" });
    await user.type(within(dialog).getByLabelText("Code"), "INTELLIGENT_AUTOMATION");
    await user.type(within(dialog).getByLabelText("Name"), "Intelligent Automation");
    await user.type(within(dialog).getByLabelText("Description"), "A description.");
    await user.type(within(dialog).getByLabelText("Value proposition"), "A proposition.");
    await user.click(within(dialog).getByRole("button", { name: "Create service" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "A service with that code already exists.",
    );
    expect(within(dialog).getByLabelText("Code")).toHaveValue("INTELLIGENT_AUTOMATION");
  });
});

describe("Deactivate and Reactivate (FR-020)", () => {
  it("Deactivate confirms the effect before sending status INACTIVE", async () => {
    const user = userEvent.setup();
    arrangeServices([automation]);
    const bodies: Schemas["ServiceUpdate"][] = [];
    server.use(
      http.patch("/api/v1/services/{id}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...automation, status: "INACTIVE" });
      }),
    );
    await openServices();
    const row = await screen.findByRole("row", { name: /Intelligent Automation/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Deactivate" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Deactivate service" });
    expect(dialog).toHaveTextContent(
      "Intelligent Automation will stop being refreshed, scored and listed; its data is kept.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Deactivate service" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "INACTIVE" }]);
    });
  });

  it("the selector's list refreshes after a status change", async () => {
    const user = userEvent.setup();
    const services = arrangeServices([automation]);
    server.use(
      http.patch("/api/v1/services/{id}", ({ response }) => {
        services[0] = { ...automation, status: "INACTIVE" };
        return response(200).json(services[0]);
      }),
    );
    await openServices();
    const row = await screen.findByRole("row", { name: /Intelligent Automation/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Deactivate" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Deactivate service" });
    await user.click(within(dialog).getByRole("button", { name: "Deactivate service" }));
    await waitFor(() => {
      expect(within(row).getByText("Inactive")).toBeInTheDocument();
    });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    expect(await screen.findByRole("menuitem", { name: "Reactivate" })).toBeInTheDocument();
  });

  it("Reactivate applies at once and shows a toast", async () => {
    const user = userEvent.setup();
    arrangeServices([legacy]);
    const bodies: Schemas["ServiceUpdate"][] = [];
    server.use(
      http.patch("/api/v1/services/{id}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...legacy, status: "ACTIVE" });
      }),
    );
    await openServices();
    const row = await screen.findByRole("row", { name: /Legacy Migration/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Reactivate" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "ACTIVE" }]);
    });
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen
          .getAllByRole("status")
          .some((element) => element.textContent.includes("Service reactivated")),
      ).toBe(true);
    });
  });

  it("a failed Reactivate shows an error callout instead of failing silently", async () => {
    const user = userEvent.setup();
    arrangeServices([legacy]);
    server.use(
      http.patch("/api/v1/services/{id}", () =>
        Response.json(
          { error: { code: "CONFLICT", message: "The service could not be reactivated." } },
          { status: 409 },
        ),
      ),
    );
    await openServices();
    const row = await screen.findByRole("row", { name: /Legacy Migration/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Reactivate" }));
    expect(await screen.findByText("The service could not be reactivated.")).toBeInTheDocument();
  });
});
