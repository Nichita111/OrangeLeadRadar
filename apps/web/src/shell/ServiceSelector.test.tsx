import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../api/queryClient";
import { adminUser, fixtureFetch } from "../features/prospect-dashboard/fixtures";
import { ServiceSelector } from "./ServiceSelector";
import { CurrentUserProvider } from "./current-user-context";
import { SelectedServiceProvider, useServiceSelection } from "./selected-service";

function Selected() {
  return <p>Selected: {useServiceSelection().service?.name ?? "none"}</p>;
}

function renderSelector() {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <CurrentUserProvider user={adminUser}>
        <SelectedServiceProvider>
          <ServiceSelector />
          <Selected />
        </SelectedServiceProvider>
      </CurrentUserProvider>
    </QueryClientProvider>,
  );
}

describe("ServiceSelector", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn(fixtureFetch()));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("FR-003: lists the active services only and starts on the first", async () => {
    renderSelector();

    await waitFor(() => {
      expect(screen.getByText("Selected: Intelligent Automation")).toBeInTheDocument();
    });
    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Intelligent Automation", "Cloud Cost Control"]);
  });

  it("FR-003: remembers the choice for the user", async () => {
    renderSelector();
    await waitFor(() => screen.getByText("Selected: Intelligent Automation"));

    fireEvent.change(screen.getByLabelText("Service"), { target: { value: "svc-3" } });

    expect(screen.getByText("Selected: Cloud Cost Control")).toBeInTheDocument();
    expect(localStorage.getItem(`leadradar.service.${adminUser.id}`)).toBe("svc-3");
  });

  it("FR-003: a stored service that is not active falls back to the first active one", async () => {
    localStorage.setItem(`leadradar.service.${adminUser.id}`, "svc-2");
    renderSelector();

    await waitFor(() => {
      expect(screen.getByText("Selected: Intelligent Automation")).toBeInTheDocument();
    });
  });
});
