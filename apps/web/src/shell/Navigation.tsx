import {
  BellIcon,
  BuildingsIcon,
  ClipboardTextIcon,
  FactoryIcon,
  GaugeIcon,
  ListChecksIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  PlugsIcon,
  ShieldCheckIcon,
  SlidersIcon,
  SparkleIcon,
  UsersIcon,
} from "@phosphor-icons/react";
import type { IconProps } from "@phosphor-icons/react";
import type { ForwardRefExoticComponent, ReactElement, RefAttributes } from "react";
import { NavLink } from "react-router";

import type { components } from "../api/schema.gen";
import { AlertsBadge } from "./AlertsBadge";

type Role = components["schemas"]["AppUserRole"];
type Icon = ForwardRefExoticComponent<IconProps & RefAttributes<SVGSVGElement>>;

const WORK: readonly [string, string, Icon][] = [
  ["/prospects", "Prospects", MagnifyingGlassIcon],
  ["/alerts", "Alerts", BellIcon],
  ["/accounts", "Accounts", BuildingsIcon],
  ["/suggested-accounts", "Suggested accounts", SparkleIcon],
  ["/runs", "Runs", PlayIcon],
  ["/labelling", "Labelling", ListChecksIcon],
];
const ADMIN: readonly [string, string, Icon][] = [
  ["/services", "Services", SlidersIcon],
  ["/settings/industries-markets", "Industries and markets", FactoryIcon],
  ["/quality", "Quality", GaugeIcon],
  ["/settings/source-plugins", "Source plug-ins", PlugsIcon],
  ["/users", "Users", UsersIcon],
  ["/audit", "Audit log", ClipboardTextIcon],
];

function Links({
  entries,
  alertCount,
}: {
  entries: readonly [string, string, Icon][];
  alertCount: number;
}) {
  return (
    <ul className="flex flex-col gap-1">
      {entries.map(([to, label, IconComponent]) => (
        <li key={to}>
          <NavLink
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-control px-3 py-2 text-sm ${isActive ? "bg-accent-soft text-accent-ink" : "text-text"}`
            }
          >
            <IconComponent size={20} />
            <span>{label}</span>
            {to === "/alerts" ? <AlertsBadge count={alertCount} /> : null}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

export function Navigation({
  userRole,
  alertCount = 0,
}: {
  userRole: Role;
  alertCount?: number;
}): ReactElement {
  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-5">
      <section aria-labelledby="work-navigation">
        <h2 id="work-navigation" className="mb-2 text-xs font-semibold text-text-tertiary">
          Work
        </h2>
        <Links entries={WORK} alertCount={alertCount} />
      </section>
      {userRole === "ADMIN" ? (
        <section aria-labelledby="admin-navigation">
          <h2
            id="admin-navigation"
            className="mb-2 flex items-center gap-1 text-xs font-semibold text-text-tertiary"
          >
            <ShieldCheckIcon size={16} /> Admin only
          </h2>
          <Links entries={ADMIN} alertCount={alertCount} />
        </section>
      ) : null}
    </nav>
  );
}
