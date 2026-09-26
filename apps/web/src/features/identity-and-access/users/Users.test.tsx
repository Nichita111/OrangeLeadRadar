import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { anaSales, errorEnvelope, olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

const neverSignedIn: Schemas["User"] = {
  id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a1a03",
  email: "new@leadradar.local",
  display_name: "New Colleague",
  role: "SALES",
  status: "ACTIVE",
  last_login_at: null,
};
const disabledUser: Schemas["User"] = {
  id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a1a04",
  email: "gone@leadradar.local",
  display_name: "Gone Person",
  role: "SALES",
  status: "DISABLED",
  last_login_at: "2026-09-01T08:00:00Z",
};

/** Arranges `API-04` with a list the test can change, and returns it. */
function arrangeUsers(initial: Schemas["User"][]): Schemas["User"][] {
  const users = [...initial];
  server.use(http.get("/api/v1/users", ({ response }) => response(200).json(users)));
  return users;
}

async function openUsers() {
  signedInAs(olgaAdmin);
  const view = renderApp("/users");
  await screen.findByRole("heading", { name: "Users", level: 1 });
  return view;
}

function rowOf(name: string): HTMLElement {
  return screen.getByRole("row", { name: new RegExp(name) });
}

describe("Users list (FR-095)", () => {
  it("lists name, email, role, status and last sign-in, and shows Never for null", async () => {
    arrangeUsers([anaSales, olgaAdmin, neverSignedIn]);
    await openUsers();
    const headers = (await screen.findAllByRole("columnheader")).map(
      (header) => header.textContent,
    );
    expect(headers).toEqual(["Name", "Email", "Role", "Status", "Last sign-in", "Actions"]);
    const ana = await screen.findByRole("row", { name: /Ana Sales/ });
    expect(within(ana).getByText("sales@leadradar.local")).toBeInTheDocument();
    expect(within(ana).getByText("Sales")).toBeInTheDocument();
    expect(within(ana).getByText("Active")).toBeInTheDocument();
    expect(within(ana).getByText(/ago$/)).toBeInTheDocument();
    expect(within(rowOf("New Colleague")).getByText("Never")).toBeInTheDocument();
    expect(within(rowOf("Olga Admin")).getByText("You")).toBeInTheDocument();
    expect(screen.getByText(/Create the people who can sign in/)).toBeInTheDocument();
  });

  it("shows the empty sentence with New user", async () => {
    arrangeUsers([]);
    await openUsers();
    expect(
      await screen.findByText("No users yet. New user creates the first one."),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "New user" })).toHaveLength(2);
  });
});

describe("Users page anatomy (FR-105, FR-107)", () => {
  it("FR-105: inside main the page header comes first, then the table, and nothing follows", async () => {
    arrangeUsers([anaSales, olgaAdmin]);
    await openUsers();
    await screen.findByRole("table");
    const main = screen.getByRole("main");
    const blocks = Array.from(main.children);
    expect(blocks.length).toBeGreaterThanOrEqual(2);
    const first = blocks[0];
    const last = blocks[blocks.length - 1];
    expect(within(first as HTMLElement).getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(within(last as HTMLElement).getByRole("table")).toBeInTheDocument();
    expect(within(main).queryByRole("contentinfo")).not.toBeInTheDocument();
  });

  it("FR-107: the status chip carries its state as text, Active or Disabled", async () => {
    arrangeUsers([olgaAdmin, disabledUser]);
    await openUsers();
    expect(
      within(await screen.findByRole("row", { name: /Gone Person/ })).getByText("Disabled"),
    ).toBeInTheDocument();
    expect(within(rowOf("Olga Admin")).getByText("Active")).toBeInTheDocument();
  });
});

describe("New user and Edit (FR-096, FR-007)", () => {
  it("New user sends UserCreate, confirms with a toast and lists the user", async () => {
    const user = userEvent.setup();
    const users = arrangeUsers([olgaAdmin]);
    const bodies: Schemas["UserCreate"][] = [];
    server.use(
      http.post("/api/v1/users", async ({ request, response }) => {
        const body = await request.json();
        bodies.push(body);
        const created: Schemas["User"] = {
          id: neverSignedIn.id,
          email: body.email,
          display_name: body.display_name,
          role: body.role,
          status: "ACTIVE",
          last_login_at: null,
        };
        users.push(created);
        return response(200).json(created);
      }),
    );
    await openUsers();
    await user.click(await screen.findByRole("button", { name: "New user" }));
    const dialog = await screen.findByRole("dialog", { name: "New user" });
    await user.type(within(dialog).getByLabelText("Email"), "new@leadradar.local");
    await user.type(within(dialog).getByLabelText("Display name"), "New Colleague");
    await user.selectOptions(within(dialog).getByLabelText("Role"), "SALES");
    await user.type(within(dialog).getByLabelText("Password"), "a long enough password");
    await user.click(within(dialog).getByRole("button", { name: "Create user" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(bodies).toEqual([
      {
        email: "new@leadradar.local",
        display_name: "New Colleague",
        role: "SALES",
        password: "a long enough password",
      },
    ]);
    expect(await screen.findByRole("row", { name: /New Colleague/ })).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen
          .getAllByRole("status")
          .some((element) => element.textContent.includes("User created")),
      ).toBe(true);
    });
  });

  it("Edit shows the email read-only and sends only the changed fields", async () => {
    const user = userEvent.setup();
    arrangeUsers([anaSales, olgaAdmin]);
    const bodies: Schemas["UserUpdate"][] = [];
    server.use(
      http.patch("/api/v1/users/{id}", async ({ request, params, response }) => {
        bodies.push(await request.json());
        expect(params.id).toBe(anaSales.id);
        return response(200).json({ ...anaSales, display_name: "Ana S." });
      }),
    );
    await openUsers();
    await user.click(
      within(await screen.findByRole("row", { name: /Ana Sales/ })).getByRole("button", {
        name: "Edit",
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Edit user" });
    const email = within(dialog).getByLabelText("Email");
    expect(email).toHaveValue("sales@leadradar.local");
    expect(email).toHaveAttribute("readonly");
    const name = within(dialog).getByLabelText("Display name");
    await user.clear(name);
    await user.type(name, "Ana S.");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ display_name: "Ana S." }]);
    });
  });

  it("a VALIDATION error on password shows beside the field with the input kept", async () => {
    const user = userEvent.setup();
    arrangeUsers([olgaAdmin]);
    server.use(
      http.post("/api/v1/users", ({ response }) =>
        response("default").json(
          errorEnvelope("VALIDATION", "The input is invalid.", {
            fields: [{ field: "/password", message: "Use at least 12 characters." }],
          }),
          { status: 422 },
        ),
      ),
    );
    await openUsers();
    await user.click(await screen.findByRole("button", { name: "New user" }));
    const dialog = await screen.findByRole("dialog", { name: "New user" });
    await user.type(within(dialog).getByLabelText("Email"), "new@leadradar.local");
    await user.type(within(dialog).getByLabelText("Display name"), "New Colleague");
    await user.type(within(dialog).getByLabelText("Password"), "short");
    await user.click(within(dialog).getByRole("button", { name: "Create user" }));
    expect(await within(dialog).findByText("Use at least 12 characters.")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Password")).toHaveAccessibleDescription(
      /Use at least 12 characters\./,
    );
    expect(within(dialog).getByLabelText("Password")).toHaveValue("short");
    expect(within(dialog).getByLabelText("Display name")).toHaveValue("New Colleague");
  });

  it("a 409 shows as a callout in the dialog with the input kept", async () => {
    const user = userEvent.setup();
    arrangeUsers([olgaAdmin]);
    server.use(
      http.post("/api/v1/users", ({ response }) =>
        response("default").json(errorEnvelope("CONFLICT", "That email is already used."), {
          status: 409,
        }),
      ),
    );
    await openUsers();
    await user.click(await screen.findByRole("button", { name: "New user" }));
    const dialog = await screen.findByRole("dialog", { name: "New user" });
    await user.type(within(dialog).getByLabelText("Email"), "admin@leadradar.local");
    await user.type(within(dialog).getByLabelText("Display name"), "Twin");
    await user.type(within(dialog).getByLabelText("Password"), "a long enough password");
    await user.click(within(dialog).getByRole("button", { name: "Create user" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "That email is already used.",
    );
    // FR-120: a failed save is a callout, never a toast.
    expect(
      screen
        .queryAllByRole("status")
        .some((element) => element.textContent.includes("already used")),
    ).toBe(false);
    expect(within(dialog).getByLabelText("Email")).toHaveValue("admin@leadradar.local");
  });
});

describe("New user and Edit dialogs (FR-123, FR-016)", () => {
  const NEW_SENTENCE =
    "The person can sign in with this email and password once you create the user; the email cannot be changed later.";
  const EDIT_SENTENCE =
    "Only the fields you change are saved; the email and everything you leave as it is stay the same.";

  it("New user: the description is the approved sentence; Cancel precedes Create user; no Close icon; first field focused", async () => {
    const user = userEvent.setup();
    arrangeUsers([olgaAdmin]);
    await openUsers();
    const opener = await screen.findByRole("button", { name: "New user" });
    await user.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "New user" });
    expect(dialog).toHaveAccessibleDescription(NEW_SENTENCE);
    expect(within(dialog).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    const buttons = within(dialog).getAllByRole("button");
    expect(buttons.map((button) => button.textContent)).toEqual(["Cancel", "Create user"]);
    expect(within(dialog).getByLabelText("Email")).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(opener).toHaveFocus();
  });

  it("Edit: the description is the approved sentence; Tab from the last field reaches Cancel, then Save", async () => {
    const user = userEvent.setup();
    arrangeUsers([anaSales, olgaAdmin]);
    await openUsers();
    await user.click(
      within(await screen.findByRole("row", { name: /Ana Sales/ })).getByRole("button", {
        name: "Edit",
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Edit user" });
    expect(dialog).toHaveAccessibleDescription(EDIT_SENTENCE);
    expect(within(dialog).queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
    within(dialog).getByLabelText("Password").focus();
    await user.tab();
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.tab();
    expect(within(dialog).getByRole("button", { name: "Save" })).toHaveFocus();
  });
});

describe("Disable and Enable (FR-097, FR-158, FR-015)", () => {
  it("the own row offers no Disable and no role field", async () => {
    const user = userEvent.setup();
    arrangeUsers([anaSales, olgaAdmin]);
    await openUsers();
    const own = await screen.findByRole("row", { name: /Olga Admin/ });
    expect(within(own).queryByRole("button", { name: "Disable" })).not.toBeInTheDocument();
    expect(within(rowOf("Ana Sales")).getByRole("button", { name: "Disable" })).toBeInTheDocument();
    await user.click(within(own).getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit user" });
    expect(within(dialog).queryByLabelText("Role")).not.toBeInTheDocument();
  });

  it("Disable confirms first, and only the confirm button sends status DISABLED", async () => {
    const user = userEvent.setup();
    arrangeUsers([anaSales, olgaAdmin]);
    const bodies: Schemas["UserUpdate"][] = [];
    server.use(
      http.patch("/api/v1/users/{id}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...anaSales, status: "DISABLED" });
      }),
    );
    await openUsers();
    await user.click(
      within(await screen.findByRole("row", { name: /Ana Sales/ })).getByRole("button", {
        name: "Disable",
      }),
    );
    const dialog = await screen.findByRole("alertdialog", { name: "Disable user" });
    expect(dialog).toHaveTextContent(
      "Ana Sales will be signed out everywhere and cannot sign in until an Admin enables them again; their feedback, labels and audit history are kept.",
    );
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(bodies).toEqual([]);
    await user.click(within(rowOf("Ana Sales")).getByRole("button", { name: "Disable" }));
    await user.click(await screen.findByRole("button", { name: "Disable user" }));
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "DISABLED" }]);
    });
    await waitFor(() => {
      expect(
        screen
          .getAllByRole("status")
          .some((element) => element.textContent.includes("User disabled")),
      ).toBe(true);
    });
  });

  it("Enable sends ACTIVE at once and shows a toast", async () => {
    const user = userEvent.setup();
    arrangeUsers([olgaAdmin, disabledUser]);
    const bodies: Schemas["UserUpdate"][] = [];
    server.use(
      http.patch("/api/v1/users/{id}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...disabledUser, status: "ACTIVE" });
      }),
    );
    await openUsers();
    await user.click(
      within(await screen.findByRole("row", { name: /Gone Person/ })).getByRole("button", {
        name: "Enable",
      }),
    );
    await waitFor(() => {
      expect(bodies).toEqual([{ status: "ACTIVE" }]);
    });
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen
          .getAllByRole("status")
          .some((element) => element.textContent.includes("User enabled")),
      ).toBe(true);
    });
  });
});

describe("Users by keyboard (FR-016, FR-008)", () => {
  it("opens New user with the keyboard and shows no internal names", async () => {
    const user = userEvent.setup();
    arrangeUsers([olgaAdmin]);
    await openUsers();
    const button = await screen.findByRole("button", { name: "New user" });
    button.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("dialog", { name: "New user" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(button).toHaveFocus();
    expect(document.body).not.toHaveTextContent(/p_positive|escalation|triage/i);
  });
});
