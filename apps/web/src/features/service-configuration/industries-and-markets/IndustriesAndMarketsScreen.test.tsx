import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const shipping: Schemas["Industry"] = {
  code: "SHIPPING",
  label: "Shipping and ports",
  status: "ACTIVE",
  account_count: 2,
};
const telecom: Schemas["Industry"] = {
  code: "TELECOM_MEDIA",
  label: "Telecom and media",
  status: "INACTIVE",
  account_count: 1,
};
const dach: Schemas["Market"] = {
  code: "DACH",
  name: "DACH",
  country_codes: ["DE", "AT", "CH"],
  status: "ACTIVE",
};

function arrange(industries: Schemas["Industry"][], markets: Schemas["Market"][]) {
  server.use(
    http.get("/api/v1/industries", ({ response }) => response(200).json(industries)),
    http.get("/api/v1/markets", ({ response }) => response(200).json(markets)),
  );
}

async function openScreen() {
  signedInAs(olgaAdmin);
  const view = renderApp("/settings/industries-markets");
  await screen.findByRole("heading", { name: "Industries and markets", level: 1 });
  return view;
}

describe("IndustriesAndMarketsScreen (FR-154)", () => {
  it("lists industries and markets, active first, with their columns", async () => {
    arrange([shipping, telecom], [dach]);
    await openScreen();
    await screen.findByRole("columnheader", { name: "Countries" });
    const industryHeaders = screen.getAllByRole("columnheader").map((header) => header.textContent);
    expect(industryHeaders).toEqual([
      "Code",
      "Label",
      "Status",
      "Accounts",
      "Actions",
      "Code",
      "Name",
      "Countries",
      "Status",
      "Actions",
    ]);
    const shippingRow = screen.getByRole("row", { name: /Shipping and ports/ });
    expect(within(shippingRow).getByText("Active")).toBeInTheDocument();
    expect(within(shippingRow).getByText("2")).toBeInTheDocument();
    const telecomRow = screen.getByRole("row", { name: /Telecom and media/ });
    expect(within(telecomRow).getByText("Retired")).toBeInTheDocument();
    const dachRow = screen.getByRole("row", { name: /DACH/ });
    expect(within(dachRow).getByText("Germany, Austria, Switzerland")).toBeInTheDocument();
  });
});

describe("New industry and New market (FR-155)", () => {
  it("New industry sends UPPER_SNAKE code and label", async () => {
    const user = userEvent.setup();
    arrange([], []);
    const bodies: Schemas["IndustryCreate"][] = [];
    server.use(
      http.post("/api/v1/industries", async ({ request, response }) => {
        const body = await request.json();
        bodies.push(body);
        return response(200).json({ ...body, status: "ACTIVE", account_count: 0 });
      }),
    );
    await openScreen();
    await user.click(await screen.findByRole("button", { name: "New industry" }));
    const dialog = await screen.findByRole("dialog", { name: "New industry" });
    await user.type(within(dialog).getByLabelText("Code"), "shipping and ports");
    await user.type(within(dialog).getByLabelText("Label"), "Shipping and ports");
    await user.click(within(dialog).getByRole("button", { name: "Create industry" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ code: "SHIPPING_AND_PORTS", label: "Shipping and ports" }]);
    });
  });

  it("New market's country multi-select stores the chosen codes", async () => {
    const user = userEvent.setup();
    arrange([], []);
    const bodies: Schemas["MarketCreate"][] = [];
    server.use(
      http.post("/api/v1/markets", async ({ request, response }) => {
        const body = await request.json();
        bodies.push(body);
        return response(200).json({ ...body, status: "ACTIVE" });
      }),
    );
    await openScreen();
    await user.click(await screen.findByRole("button", { name: "New market" }));
    const dialog = await screen.findByRole("dialog", { name: "New market" });
    await user.type(within(dialog).getByLabelText("Code"), "DACH");
    await user.type(within(dialog).getByLabelText("Name"), "DACH");
    await user.click(within(dialog).getByRole("checkbox", { name: /Germany/ }));
    await user.click(within(dialog).getByRole("checkbox", { name: /Austria/ }));
    await user.click(within(dialog).getByRole("button", { name: "Create market" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ code: "DACH", name: "DACH", country_codes: ["DE", "AT"] }]);
    });
  });
});

describe("Rename, Retire and Restore (FR-156)", () => {
  it("Retire confirms with the picker note, then sends status INACTIVE", async () => {
    const user = userEvent.setup();
    arrange([shipping], []);
    const bodies: Schemas["IndustryUpdate"][] = [];
    server.use(
      http.patch("/api/v1/industries/{code}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...shipping, status: "INACTIVE" });
      }),
    );
    await openScreen();
    const row = await screen.findByRole("row", { name: /Shipping and ports/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Retire" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Retire industry" });
    expect(dialog).toHaveTextContent(
      "Shipping and ports will leave every picker; accounts and saved scoring versions that already use it keep it.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Retire industry" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "INACTIVE" }]);
    });
  });

  it("Restore sends status ACTIVE after confirming", async () => {
    const user = userEvent.setup();
    arrange([telecom], []);
    const bodies: Schemas["IndustryUpdate"][] = [];
    server.use(
      http.patch("/api/v1/industries/{code}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...telecom, status: "ACTIVE" });
      }),
    );
    await openScreen();
    const row = await screen.findByRole("row", { name: /Telecom and media/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Restore" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Restore industry" });
    await user.click(within(dialog).getByRole("button", { name: "Restore industry" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "ACTIVE" }]);
    });
  });

  it("Rename opens the dialog with the code read-only and sends only the label", async () => {
    const user = userEvent.setup();
    arrange([shipping], []);
    const bodies: Schemas["IndustryUpdate"][] = [];
    server.use(
      http.patch("/api/v1/industries/{code}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...shipping, label: "Shipping" });
      }),
    );
    await openScreen();
    const row = await screen.findByRole("row", { name: /Shipping and ports/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }));
    const dialog = await screen.findByRole("dialog", { name: "Rename industry" });
    const code = within(dialog).getByLabelText("Code");
    expect(code).toHaveValue("SHIPPING");
    expect(code).toHaveAttribute("readonly");
    const label = within(dialog).getByLabelText("Label");
    await user.clear(label);
    await user.type(label, "Shipping");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ label: "Shipping" }]);
    });
  });

  it("a failed Retire shows an error callout instead of failing silently", async () => {
    const user = userEvent.setup();
    arrange([shipping], []);
    server.use(
      http.patch("/api/v1/industries/{code}", () =>
        Response.json(
          { error: { code: "CONFLICT", message: "The industry could not be retired." } },
          { status: 409 },
        ),
      ),
    );
    await openScreen();
    const row = await screen.findByRole("row", { name: /Shipping and ports/ });
    await user.click(within(row).getByRole("button", { name: /Actions for/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Retire" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Retire industry" });
    await user.click(within(dialog).getByRole("button", { name: "Retire industry" }));
    expect(await screen.findByText("The industry could not be retired.")).toBeInTheDocument();
  });
});
