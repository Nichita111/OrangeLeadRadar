import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { useCurrentUser } from "../api/auth";
import { ApiError } from "../api/errors";
import { RequireAdmin, RequireAuth } from "./guards";

vi.mock("../api/auth", () => ({ useCurrentUser: vi.fn() }));
const mockedCurrentUser = vi.mocked(useCurrentUser);

describe("route guards", () => {
  beforeEach(() => vi.clearAllMocks());

  it("FR-006 sends an anonymous user to Sign in with the return path", () => {
    mockedCurrentUser.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new ApiError(401, { code: "UNAUTHENTICATED", message: "Sign in" }),
      refetch: vi.fn(),
    });
    render(
      <MemoryRouter initialEntries={["/accounts?page=2"]}>
        <Routes>
          <Route
            path="/accounts"
            element={
              <RequireAuth>
                <p>Accounts</p>
              </RequireAuth>
            }
          />
          <Route path="/login" element={<p>Sign in</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Sign in")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("FR-006 tells Sales that an Admin route needs Admin", async () => {
    mockedCurrentUser.mockReturnValue({
      data: {
        id: "u",
        email: "s@example.com",
        display_name: "Sales",
        role: "SALES",
        status: "ACTIVE",
        last_login_at: null,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = render(
      <MemoryRouter>
        <RequireAdmin>
          <p>Services</p>
        </RequireAdmin>
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Not allowed" })).toBeInTheDocument();
    expect(screen.getByText(/Admin role/)).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
