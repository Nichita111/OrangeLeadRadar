import type { ReactNode } from "react";
import { useMatches } from "react-router";

import type { Schemas } from "../api/contract";
import { CurrentUserProvider } from "./CurrentUser";
import { Header } from "./Header";
import { Navigation } from "./Navigation";
import { isRouteHandle } from "./routeHandle";
import { SelectedServiceProvider } from "./SelectedService";
import { UserCard } from "./UserCard";

/** WF-01: the left navigation with the user card, the header, and the screen content. */
export function AppShell({
  user,
  children,
}: {
  user: Schemas["AuthenticatedUser"];
  children: ReactNode;
}) {
  const handles = useMatches().flatMap((match) =>
    isRouteHandle(match.handle) ? [match.handle] : [],
  );
  return (
    <CurrentUserProvider user={user}>
      <SelectedServiceProvider>
        <div className="grid min-h-screen grid-cols-[260px_1fr]">
          <aside className="flex flex-col justify-between gap-6 border-r border-border bg-surface p-4">
            <div className="flex flex-col gap-6">
              <div className="px-3 text-section font-semibold">LeadRadar</div>
              <Navigation isAdmin={user.role === "ADMIN"} />
            </div>
            <UserCard />
          </aside>
          <div className="flex min-w-0 flex-col">
            <Header handle={handles.at(-1) ?? null} />
            <main className="flex flex-1 flex-col gap-6 p-8">{children}</main>
          </div>
        </div>
      </SelectedServiceProvider>
    </CurrentUserProvider>
  );
}
