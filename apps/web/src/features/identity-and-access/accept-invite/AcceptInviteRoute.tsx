import { lazy, Suspense } from "react";

const AcceptInvite = lazy(() =>
  import("./AcceptInvite").then((module) => ({ default: module.AcceptInvite })),
);

/** Route `/invite`: Accept invite, loaded lazily with its scene (FR-173). */
export function AcceptInviteRoute() {
  return (
    <Suspense fallback={null}>
      <AcceptInvite />
    </Suspense>
  );
}
