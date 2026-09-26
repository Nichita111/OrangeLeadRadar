import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { useSignOut } from "../api/auth";
import { UserCard } from "./UserCard";

vi.mock("../api/auth", () => ({ useSignOut: vi.fn() }));
const mockedSignOut = vi.mocked(useSignOut);

describe("UserCard", () => {
  it("FR-004 shows the user and signs out to Sign in", async () => {
    mockedSignOut.mockReturnValue({
      mutate: (_value, options) => {
        const onSuccess = options?.onSuccess as (() => void) | undefined;
        onSuccess?.();
      },
    } as ReturnType<typeof useSignOut>);
    render(
      <MemoryRouter initialEntries={["/prospects"]}>
        <Routes>
          <Route
            path="/prospects"
            element={
              <UserCard
                user={{
                  id: "u",
                  email: "ana@example.com",
                  display_name: "Ana Sales",
                  role: "SALES",
                }}
              />
            }
          />
          <Route path="/login" element={<p>Sign in</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Ana Sales")).toBeInTheDocument();
    expect(screen.getByText("Sales")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(screen.getByText("Sign in")).toBeInTheDocument();
  });
});
