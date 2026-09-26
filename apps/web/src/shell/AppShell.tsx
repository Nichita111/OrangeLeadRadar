import type { ReactElement } from "react";
import { Outlet } from "react-router";

import { useUnreadAlertCount } from "../api/alerts";
import { useCurrentUser } from "../api/auth";
import { ApiError } from "../api/errors";
import { useConfig } from "./config";
import { Header } from "./Header";
import { Navigation } from "./Navigation";
import { ServiceSelector, ServiceSelectorProvider, useSelectedService } from "./ServiceSelector";
import { ErrorState } from "./states/ErrorState";
import { LoadingRows } from "./states/LoadingRows";
import { UnavailableState } from "./states/UnavailableState";
import { UserCard } from "./UserCard";

function ShellContent(): ReactElement | null {
  const { data: user } = useCurrentUser();
  const service = useSelectedService();
  const config = useConfig();
  const unreadQuery = useUnreadAlertCount(service?.id, config.ALERT_POLL_INTERVAL_MS);
  if (user === undefined) return null;
  if (service !== undefined && unreadQuery.isPending) return <LoadingRows />;
  if (
    unreadQuery.error instanceof ApiError &&
    (unreadQuery.error.status === 503 ||
      (unreadQuery.error.status === 429 && unreadQuery.error.code === "BUDGET_EXHAUSTED"))
  )
    return <UnavailableState error={unreadQuery.error} />;
  if (unreadQuery.error instanceof Error)
    return (
      <ErrorState
        message={unreadQuery.error.message}
        retry={() => {
          void unreadQuery.refetch();
        }}
      />
    );
  const unread = unreadQuery.data ?? 0;
  return (
    <div className="grid min-h-screen grid-cols-[15rem_1fr] bg-page text-text">
      <aside className="flex flex-col border-r border-border bg-surface p-4">
        <strong className="mb-6 text-lg">LeadRadar</strong>
        <Navigation userRole={user.role} alertCount={unread} />
        <div className="mt-auto">
          <UserCard user={user} />
        </div>
      </aside>
      <div>
        <Header selector={<ServiceSelector />} />
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function AppShell(): ReactElement | null {
  const { data: user } = useCurrentUser();
  if (user === undefined) return null;
  return (
    <ServiceSelectorProvider userId={user.id}>
      <ShellContent />
    </ServiceSelectorProvider>
  );
}
