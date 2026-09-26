/**
 * A static placeholder shape, sized like the row or card it stands in for
 * ([FR-118](/architecture/services/frontend.md#states)). Skeleton loading is not a listed
 * [Motion](/architecture/services/frontend.md#motion) pattern, so it never animates
 * ([FR-124](/architecture/services/frontend.md#motion)).
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`rounded-control bg-border ${className}`} aria-hidden="true" />;
}
