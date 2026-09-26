import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../../api/queryClient";
import { SignInScreen } from "./SignInScreen";

function renderSignIn() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<SignInScreen />} />
          <Route path="/prospects" element={<div>Prospects screen</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fillAndSubmit(email: string, password: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("SignInScreen", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("FR-152: carries a hint under the email and password fields", () => {
    renderSignIn();

    expect(screen.getByText(/address the admin created/i)).toBeInTheDocument();
    expect(screen.getByText(/lock the account/i)).toBeInTheDocument();
  });

  it("FR-093: on success, goes to /prospects", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            { id: "1", email: "ana@leadradar.local", display_name: "Ana", role: "SALES" },
            200,
          ),
        ),
      ),
    );

    renderSignIn();
    fillAndSubmit("ana@leadradar.local", "correct-password");

    await waitFor(() => {
      expect(screen.getByText("Prospects screen")).toBeInTheDocument();
    });
  });

  it("FR-094: shows the locked message with the minutes remaining", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: "LOCKED",
                message: "Too many failed sign-ins.",
                details: { retry_after_min: 15 },
              },
            },
            423,
          ),
        ),
      ),
    );

    renderSignIn();
    fillAndSubmit("ana@leadradar.local", "wrong-password");

    await waitFor(() => {
      expect(screen.getByText(/try again in 15 minutes/i)).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Email")).toHaveValue("ana@leadradar.local");
  });

  it("FR-094: shows a disabled-account message on a 403", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            { error: { code: "FORBIDDEN", message: "Not allowed for this account." } },
            403,
          ),
        ),
      ),
    );

    renderSignIn();
    fillAndSubmit("ana@leadradar.local", "correct-password");

    await waitFor(() => {
      expect(screen.getByText(/account has been disabled/i)).toBeInTheDocument();
    });
  });

  it("FR-094: shows the api's message on wrong credentials", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            { error: { code: "UNAUTHENTICATED", message: "Incorrect email or password." } },
            401,
          ),
        ),
      ),
    );

    renderSignIn();
    fillAndSubmit("ana@leadradar.local", "wrong-password");

    await waitFor(() => {
      expect(screen.getByText("Incorrect email or password.")).toBeInTheDocument();
    });
  });
});
