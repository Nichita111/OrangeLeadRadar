import { cn } from "./cn";

/** A static placeholder shape the size of what it stands in for (FR-118, FR-126). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-control bg-border", className)} />;
}
