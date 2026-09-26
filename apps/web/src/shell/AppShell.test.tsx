import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { useUnreadAlertCount } from "../api/alerts";
import { useCurrentUser } from "../api/auth";
import { ConfigProvider, type ClientConfig } from "./config";
import { AppShell } from "./AppShell";

vi.mock("../api/alerts", () => ({ useUnreadAlertCount: vi.fn() }));
vi.mock("../api/auth", () => ({ useCurrentUser: vi.fn(), useSignOut: vi.fn() }));
vi.mock("./ServiceSelector", () => ({
  ServiceSelector: () => <span>Service selector</span>,
  ServiceSelectorProvider: ({ children }: { children: React.ReactNode }) => children,
  useSelectedService: () => ({ id: "service-1" }),
}));
vi.mock("./Header", () => ({ Header: () => <header>Header</header> }));
vi.mock("./Navigation", () => ({
  Navigation: ({ alertCount }: { alertCount?: number }) => <nav>Alerts {alertCount}</nav>,
}));
vi.mock("./UserCard", () => ({ UserCard: () => <div>User</div> }));

const config: ClientConfig = {
  RUN_POLL_INTERVAL_MS: 2_000,
  ALERT_POLL_INTERVAL_MS: 60_000,
  CONFIDENCE_HIGH_MIN: 0.85,
  CONFIDENCE_MEDIUM_MIN: 0.65,
  MOCK_API: false,
};

const mockedCurrentUser = vi.mocked(useCurrentUser);
const mockedUnreadCount = vi.mocked(useUnreadAlertCount);

function renderShell() {
  return render(
    <ConfigProvider value={config}>
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>
    </ConfigProvider>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    mockedCurrentUser.mockReturnValue({
      data: {
        id: "user-1",
        email: "sales@example.com",
        display_name: "Sales",
        role: "SALES",
      },
    } as ReturnType<typeof useCurrentUser>);
  });

  it("FR-005 preserves the unread-alert loading state", async () => {
    mockedUnreadCount.mockReturnValue({ isPending: true } as ReturnType<
      typeof useUnreadAlertCount
    >);
    const { container } = renderShell();
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect((await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations).toEqual([]);
  });

  it("FR-005 preserves the unread-alert error and retries", () => {
    const refetch = vi.fn();
    mockedUnreadCount.mockReturnValue({
      isPending: false,
      error: new Error("Alerts failed"),
      refetch,
    } as ReturnType<typeof useUnreadAlertCount>);
    renderShell();
    expect(screen.getByText("Alerts failed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledOnce();
  });
});
