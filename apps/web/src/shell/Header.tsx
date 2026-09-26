/**
 * `FR-102`: the header shows the current screen as a breadcrumb, and every Admin screen carries
 * an Admin only chip. Account detail is nested: its breadcrumb is a link to its parent,
 * Prospects, then "Account detail". The header also holds the service selector (`FR-003`).
 */
import { Link, matchPath, useLocation } from "react-router-dom";

import { Chip } from "../components/Chip";
import { ServiceSelector } from "./ServiceSelector";
import { navRegistry } from "./nav-registry";

export function Header() {
  const location = useLocation();
  const entry = navRegistry.find((candidate) => location.pathname.startsWith(candidate.to));
  const isAccountDetail = matchPath("/accounts/:id", location.pathname) !== null;

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-surface px-6">
      {isAccountDetail ? (
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[15px]">
          <Link to="/prospects" className="font-semibold text-text-secondary hover:text-text">
            Prospects
          </Link>
          <span aria-hidden="true" className="text-text-tertiary">
            /
          </span>
          <span aria-current="page" className="font-semibold text-text">
            Account detail
          </span>
        </nav>
      ) : (
        <span className="text-[15px] font-semibold text-text">{entry?.label}</span>
      )}
      {entry?.roles === "admin" && <Chip tone="neutral">Admin only</Chip>}
      <ServiceSelector />
    </header>
  );
}
