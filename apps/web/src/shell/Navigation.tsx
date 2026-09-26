import {
  ArrowsClockwiseIcon,
  BellIcon,
  BuildingsIcon,
  FactoryIcon,
  PuzzlePieceIcon,
  ReceiptIcon,
  SealCheckIcon,
  SlidersHorizontalIcon,
  SparkleIcon,
  TagIcon,
  TargetIcon,
  UsersIcon,
  type Icon,
} from "@phosphor-icons/react";
import { NavLink } from "react-router";

import { cn } from "../components/cn";
import { ADMIN_ENTRIES, WORK_ENTRIES, type NavEntry, type NavIconName } from "./navigationEntries";

const ICONS: Record<NavIconName, Icon> = {
  Target: TargetIcon,
  Bell: BellIcon,
  Buildings: BuildingsIcon,
  Sparkle: SparkleIcon,
  ArrowsClockwise: ArrowsClockwiseIcon,
  Tag: TagIcon,
  SlidersHorizontal: SlidersHorizontalIcon,
  Factory: FactoryIcon,
  SealCheck: SealCheckIcon,
  PuzzlePiece: PuzzlePieceIcon,
  Users: UsersIcon,
  Receipt: ReceiptIcon,
};

function Group({ heading, entries }: { heading: string; entries: NavEntry[] }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="m-0 px-3 text-hint font-semibold text-text-tertiary">{heading}</h2>
      <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
        {entries.map((entry) => {
          const EntryIcon = ICONS[entry.icon];
          return (
            <li key={entry.route}>
              <NavLink
                to={entry.route}
                className={({ isActive }) =>
                  cn(
                    "flex h-control items-center gap-2.5 rounded-control px-3 text-text no-underline hover:bg-page",
                    // The current entry: tint, weight and aria-current, never colour alone (FR-101).
                    isActive && "bg-accent-soft font-semibold text-accent-ink",
                  )
                }
              >
                <EntryIcon size={20} data-icon={entry.icon} aria-hidden />
                {entry.label}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** FR-001, FR-101: the Work group for everyone, the Admin only group for Admins. */
export function Navigation({ isAdmin }: { isAdmin: boolean }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      <Group heading="Work" entries={WORK_ENTRIES} />
      {isAdmin && <Group heading="Admin only" entries={ADMIN_ENTRIES} />}
    </nav>
  );
}
