import type { ReactElement } from "react";
import { Link, matchPath, useLocation } from "react-router";

const ROUTES: readonly [string, string, string | undefined][] = [
  ["/accounts/:id/profile", "Account profile", "/accounts"],
  ["/accounts/:id/outreach", "Outreach composer", "/accounts"],
  ["/accounts/:id", "Account detail", "/accounts"],
  ["/services/:id/scoring", "Scoring settings", "/services"],
  ["/services/:id", "Service editor", "/services"],
  ["/settings/industries-markets", "Industries and markets", undefined],
  ["/settings/source-plugins", "Source plug-ins", undefined],
  ["/suggested-accounts", "Suggested accounts", undefined],
  ["/prospects", "Prospects", undefined],
  ["/alerts", "Alerts", undefined],
  ["/accounts", "Accounts", undefined],
  ["/runs", "Runs", undefined],
  ["/labelling", "Labelling", undefined],
  ["/services", "Services", undefined],
  ["/quality", "Quality report", undefined],
  ["/users", "Users", undefined],
  ["/audit", "Audit log", undefined],
];
const ADMIN_PREFIXES = ["/services", "/settings", "/quality", "/users", "/audit"];

export function Header({ selector }: { selector?: ReactElement }): ReactElement {
  const { pathname } = useLocation();
  const route = ROUTES.find(([pattern]) => matchPath({ path: pattern, end: true }, pathname));
  const label = route?.[1] ?? "LeadRadar";
  const parent = route?.[2];
  const parentLabel =
    parent === undefined ? undefined : ROUTES.find(([path]) => path === parent)?.[1];
  const isAdmin = ADMIN_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  return (
    <header className="flex min-h-16 items-center justify-between border-b border-border px-6">
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm">
        {parent !== undefined ? (
          <>
            <Link className="text-text-secondary" to={parent}>
              {parentLabel}
            </Link>
            <span aria-hidden="true">/</span>
          </>
        ) : null}
        <span aria-current="page" className="font-medium text-text">
          {label}
        </span>
        {isAdmin ? (
          <span className="rounded-full bg-cool-soft px-2 py-1 text-xs text-cool">Admin only</span>
        ) : null}
      </nav>
      {selector}
    </header>
  );
}
