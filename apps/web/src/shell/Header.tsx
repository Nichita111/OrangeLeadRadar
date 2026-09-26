import { Chip } from "../components/Chip";
import type { RouteHandle } from "./routeHandle";

/** FR-102: the current screen as a breadcrumb, and the Admin only chip on Admin screens. */
export function Header({ handle }: { handle: RouteHandle | null }) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-8">
      <ol aria-label="Breadcrumb" className="m-0 flex list-none items-center gap-2 p-0">
        {handle !== null && (
          <li aria-current="page" className="font-semibold">
            {handle.title}
          </li>
        )}
      </ol>
      {handle?.adminOnly === true && <Chip tone="accent">Admin only</Chip>}
    </header>
  );
}
