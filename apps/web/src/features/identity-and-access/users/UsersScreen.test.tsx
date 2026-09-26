import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthenticatedUser } from "../../../api/auth";
import { createQueryClient } from "../../../api/queryClient";
import type { User } from "../../../api/users";
import { ToastProvider } from "../../../components/Toast";
import { CurrentUserProvider } from "../../../shell/current-user-context";
import { UsersScreen } from "./UsersScreen";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface FetchState {
  users: User[];
}

function stubUsersFetch(state: FetchState) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL, init?: RequestInit) => {
      const url = input.toString();
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/v1/users") && method === "GET") {
        return Promise.resolve(jsonResponse(state.users, 200));
      }
      if (url.endsWith("/api/v1/users") && method === "POST") {
        const body = JSON.parse(init?.body as string) as {
          email: string;
          display_name: string;
          role: User["role"];
        };
        const created: User = {
          id: "new-user",
          email: body.email,
          display_name: body.display_name,
          role: body.role,
          status: "ACTIVE",
          last_login_at: null,
        };
        state.users = [...state.users, created];
        return Promise.resolve(jsonResponse(created, 200));
      }
      const patchMatch = /\/api\/v1\/users\/([^/]+)$/.exec(url);
      if (patchMatch && method === "PATCH") {
        const id = patchMatch[1];
        const body = JSON.parse(init?.body as string) as Partial<User>;
        state.users = state.users.map((user) => (user.id === id ? { ...user, ...body } : user));
        const updated = state.users.find((user) => user.id === id);
        return Promise.resolve(jsonResponse(updated, 200));
      }
      return Promise.resolve(
        jsonResponse({ error: { code: "NOT_FOUND", message: "Not found." } }, 404),
      );
    }),
  );
}

const admin: AuthenticatedUser = {
  id: "admin-1",
  email: "admin@leadradar.local",
  display_name: "Olga Admin",
  role: "ADMIN",
};

const sales: User = {
  id: "sales-1",
  email: "sales@leadradar.local",
  display_name: "Ana Sales",
  role: "SALES",
  status: "ACTIVE",
  last_login_at: "2026-09-25T10:00:00Z",
};

function renderUsersScreen(users: User[], currentUser: AuthenticatedUser = admin) {
  const state: FetchState = { users };
  stubUsersFetch(state);
  render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <CurrentUserProvider user={currentUser}>
          <UsersScreen />
        </CurrentUserProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return state;
}

const adminRow: User = {
  id: "admin-1",
  email: "admin@leadradar.local",
  display_name: "Olga Admin",
  role: "ADMIN",
  status: "ACTIVE",
  last_login_at: null,
};

describe("UsersScreen", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("FR-095: lists users with name, email, role, status and last sign-in", async () => {
    renderUsersScreen([sales, adminRow]);

    await waitFor(() => {
      expect(screen.getByText("Ana Sales")).toBeInTheDocument();
    });
    const row = screen.getByText("Ana Sales").closest("tr");
    expect(row).not.toBeNull();
    const withinRow = within(row as HTMLElement);
    expect(withinRow.getByText("sales@leadradar.local")).toBeInTheDocument();
    expect(withinRow.getByText("Sales")).toBeInTheDocument();
    expect(withinRow.getByText("Active")).toBeInTheDocument();
  });

  it("FR-096: New user creates an account", async () => {
    renderUsersScreen([adminRow]);
    await waitFor(() => screen.getByText("Olga Admin"));

    fireEvent.click(screen.getByRole("button", { name: "New user" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "nina@leadradar.local" } });
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Nina Sales" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-strong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    await waitFor(() => {
      expect(screen.getByText("Nina Sales")).toBeInTheDocument();
    });
  });

  it("FR-097: the signed-in Admin's own row offers neither Disable nor a role change", async () => {
    renderUsersScreen([sales, adminRow]);
    await waitFor(() => screen.getByText("Olga Admin"));

    expect(screen.queryByRole("button", { name: "Disable Olga Admin" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable Ana Sales" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit Olga Admin" }));
    expect(screen.getByText(/you cannot change your own role/i)).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Role" })).not.toBeInTheDocument();
  });

  it("FR-015, FR-123: disabling a user asks for confirmation before it applies", async () => {
    const state = renderUsersScreen([sales, adminRow]);
    await waitFor(() => screen.getByText("Ana Sales"));

    fireEvent.click(screen.getByRole("button", { name: "Disable Ana Sales" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Disable user" })).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(state.users.find((user) => user.id === sales.id)?.status).toBe("ACTIVE");

    fireEvent.click(screen.getByRole("button", { name: "Disable Ana Sales" }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Disable user" }),
    );

    await waitFor(() => {
      expect(state.users.find((user) => user.id === sales.id)?.status).toBe("DISABLED");
    });
  });

  it("FR-005: shows the api's error message with a Retry action", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ error: { code: "INTERNAL", message: "Something broke." } }, 500),
        ),
      ),
    );
    render(
      <QueryClientProvider client={createQueryClient()}>
        <ToastProvider>
          <CurrentUserProvider user={admin}>
            <UsersScreen />
          </CurrentUserProvider>
        </ToastProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Something broke.")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
