/**
 * The left navigation of [Navigation](/architecture/services/frontend.md#navigation) (`FR-001`,
 * `FR-101`): grouped under Work and Admin only, every entry with an icon and its label, the
 * current entry tinted and carrying `aria-current`, never colour alone.
 */
import { NavLink } from "react-router-dom";

import type { AppUserRole } from "../api/users";
import { NAV_GROUP_LABELS, navRegistry, type NavGroup } from "./nav-registry";

const GROUPS: NavGroup[] = ["work", "admin"];

export function Navigation({ role }: { role: AppUserRole }) {
  return (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 py-4">
      {GROUPS.map((group) => {
        const entries = navRegistry.filter(
          (entry) => entry.group === group && (entry.roles === "any" || role === "ADMIN"),
        );
        if (entries.length === 0) {
          return null;
        }
        return (
          <div key={group} className="flex flex-col gap-1">
            <h2 className="px-3 text-[12.5px] font-medium uppercase tracking-wide text-text-tertiary">
              {NAV_GROUP_LABELS[group]}
            </h2>
            <ul className="flex flex-col gap-0.5">
              {entries.map((entry) => (
                <li key={entry.to}>
                  <NavLink
                    to={entry.to}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 rounded-control px-3 py-2 text-sm font-medium ${
                        isActive
                          ? "bg-accent-soft text-accent-ink"
                          : "text-text-secondary hover:bg-page hover:text-text"
                      }`
                    }
                  >
                    <entry.icon size={20} aria-hidden="true" />
                    {entry.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
