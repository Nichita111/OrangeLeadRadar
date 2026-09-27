import { lazy, Suspense } from "react";
import { Navigate } from "react-router";

import { useMe } from "../../api/authenticationAndUsers";

const Landing = lazy(() => import("./Landing").then((module) => ({ default: module.Landing })));

/** Route `/`: a signed-in user goes to Prospects (FR-163); anyone else sees Landing, loaded lazily (FR-166). */
export function LandingRoute() {
  const me = useMe();
  if (me.status === "success") {
    return <Navigate to="/prospects" replace />;
  }
  if (me.status === "pending") {
    return null;
  }
  return (
    <Suspense fallback={null}>
      <Landing />
    </Suspense>
  );
}
