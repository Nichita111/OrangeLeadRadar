/** Test helper: mounts a screen at a route inside the providers the shell gives it, with `fetch`
 * answered by `fixtureFetch`. */
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { vi } from "vitest";

import { RUNTIME_CONFIG_DEFAULTS } from "../../api/config";
import { createQueryClient } from "../../api/queryClient";
import { ToastProvider } from "../../components/Toast";
import { ConfigProvider } from "../../shell/config-context";
import { CurrentUserProvider } from "../../shell/current-user-context";
import { SelectedServiceProvider } from "../../shell/selected-service";
import { adminUser, fixtureFetch, type FixtureOverrides } from "./fixtures";

function CurrentLocation() {
  const location = useLocation();
  return <p data-testid="location">{location.pathname + location.search}</p>;
}

export function renderScreen(
  routePath: string,
  screen: React.ReactNode,
  url: string,
  overrides: FixtureOverrides = {},
) {
  const fetchSpy = vi.fn(fixtureFetch(overrides));
  vi.stubGlobal("fetch", fetchSpy);
  render(
    <ConfigProvider value={RUNTIME_CONFIG_DEFAULTS}>
      <QueryClientProvider client={createQueryClient()}>
        <ToastProvider>
          <CurrentUserProvider user={overrides.user ?? adminUser}>
            <SelectedServiceProvider>
              <MemoryRouter initialEntries={[url]}>
                <Routes>
                  <Route path={routePath} element={screen} />
                </Routes>
                <CurrentLocation />
              </MemoryRouter>
            </SelectedServiceProvider>
          </CurrentUserProvider>
        </ToastProvider>
      </QueryClientProvider>
    </ConfigProvider>,
  );
  return fetchSpy;
}
