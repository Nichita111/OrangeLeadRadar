/**
 * WF-01 — application shell: the left navigation, the header and the screen content, the same
 * parts in the same order on every signed-in screen ([Navigation]
 * (/architecture/services/frontend.md#navigation)).
 */
import { Outlet } from "react-router-dom";

import { Header } from "./Header";
import { Navigation } from "./Navigation";
import { UserCard } from "./UserCard";
import { useCurrentUser } from "./current-user-context";

export function AppShell() {
  const user = useCurrentUser();

  return (
    <div className="flex h-screen bg-page">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
        <div className="px-4 py-4">
          <span className="text-[15px] font-semibold text-text">LeadRadar</span>
        </div>
        <Navigation role={user.role} />
        <UserCard />
      </aside>
      <div className="flex flex-1 flex-col overflow-y-auto">
        <Header />
        <main className="flex-1 px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
