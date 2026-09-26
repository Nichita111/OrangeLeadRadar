import { Navigate, Outlet, useLocation } from "react-router";

import { useMe } from "../api/authenticationAndUsers";
import { ApiError } from "../api/client";
import { ButtonLink } from "../components/Button";
import { Skeleton } from "../components/Skeleton";
import { AppShell } from "./AppShell";
import { DataView } from "./states/DataView";

/**
 * FR-006: resolves the session. A `401` goes to Sign in with the current route as return path; any
 * other error is shown as the error or unavailable state; a session opens the shell.
 */
export function RequireSession() {
  const me = useMe();
  const location = useLocation();
  if (me.status === "error" && me.error instanceof ApiError && me.error.status === 401) {
    const back = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?return=${back}`} replace />;
  }
  return (
    <DataView
      query={me}
      isEmpty={() => false}
      skeleton={<Skeleton className="m-8 h-40" />}
      empty={{
        message: "There is no session.",
        action: <ButtonLink to="/login">Sign in</ButtonLink>,
      }}
    >
      {(user) => (
        <AppShell user={user}>
          <Outlet />
        </AppShell>
      )}
    </DataView>
  );
}
