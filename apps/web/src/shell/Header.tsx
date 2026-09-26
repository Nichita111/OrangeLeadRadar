/**
 * `FR-102`: the header shows the current screen as a breadcrumb, and every Admin screen carries
 * an Admin only chip. No screen this task builds is nested, so there is no parent link yet.
 */
import { useLocation } from "react-router-dom";

import { Chip } from "../components/Chip";
import { navRegistry } from "./nav-registry";

export function Header() {
  const location = useLocation();
  const entry = navRegistry.find((candidate) => location.pathname.startsWith(candidate.to));

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface px-6">
      <span className="text-[15px] font-semibold text-text">{entry?.label}</span>
      {entry?.roles === "admin" && <Chip tone="neutral">Admin only</Chip>}
    </header>
  );
}
