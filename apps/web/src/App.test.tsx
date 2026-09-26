import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { RUNTIME_CONFIG_DEFAULTS } from "./api/config";
import { createQueryClient } from "./api/queryClient";
import { ToastProvider } from "./components/Toast";
import { ConfigProvider } from "./shell/config-context";

function renderApp(initialPath: string) {
  return render(
    <ConfigProvider value={RUNTIME_CONFIG_DEFAULTS}>
      <QueryClientProvider client={createQueryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <App />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ConfigProvider>,
  );
}

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 401 }))),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("FR-006: sends an anonymous visitor to Sign in with the current route as return path", async () => {
    renderApp("/users");

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    });
  });
});
