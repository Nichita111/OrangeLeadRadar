import type { ReactElement } from "react";

export function AlertsBadge({ count }: { count: number }): ReactElement | null {
  return count > 0 ? (
    <span
      className="ml-auto rounded-full bg-accent px-2 font-mono text-xs text-on-accent"
      aria-label={`${String(count)} unread alerts`}
    >
      {count}
    </span>
  ) : null;
}
