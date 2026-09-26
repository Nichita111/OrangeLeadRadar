/**
 * The one array of [Navigation](/architecture/services/frontend.md#navigation) entries
 * (`FR-001`). Each entry is a screen that exists; a task that adds a screen appends its entry
 * here, never redefining the list. `group` is the heading of [Page anatomy]
 * (/architecture/services/frontend.md#page-anatomy) the entry sits under; `roles` is `"any"` or
 * `"admin"`, matching the roles column of the frontend's [Routes]
 * (/architecture/services/frontend.md#routes).
 */
import { ArrowsClockwiseIcon, BuildingsIcon, UsersIcon, type Icon } from "@phosphor-icons/react";

export type NavGroup = "work" | "admin";
export type NavRoles = "any" | "admin";

export interface NavEntry {
  to: string;
  label: string;
  icon: Icon;
  group: NavGroup;
  roles: NavRoles;
}

export const NAV_GROUP_LABELS: Record<NavGroup, string> = {
  work: "Work",
  admin: "Admin only",
};

export const navRegistry: NavEntry[] = [
  { to: "/users", label: "Users", icon: UsersIcon, group: "admin", roles: "admin" },
  { to: "/accounts", label: "Accounts", icon: BuildingsIcon, group: "work", roles: "any" },
  { to: "/runs", label: "Runs", icon: ArrowsClockwiseIcon, group: "work", roles: "any" },
];
