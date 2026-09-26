import type { ReactElement, ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { useCurrentUser } from "../api/auth";
import { ApiError } from "../api/errors";
import { ErrorState } from "./states/ErrorState";
import { NotAllowed } from "./NotAllowed";

/**
 * `FR-006`: a `401` from the current-user query sends the user to Sign in with the current
 * route as return path. A query or mutation error elsewhere is handled globally by the query
 * client ([providers](providers.tsx)).
 */
export function RequireAuth({ children }: { children: ReactNode }): ReactElement | null {
  const location = useLocation();
  const { isPending, isError, error, refetch } = useCurrentUser();

  if (isPending) {
    return null;
  }
  if (error instanceof ApiError && error.status === 401) {
    const returnPath = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?return=${encodeURIComponent(returnPath)}`} replace />;
  }
  if (isError && error instanceof Error)
    return (
      <ErrorState
        message={error.message}
        retry={() => {
          void refetch();
        }}
      />
    );
  if (isError) throw new Error("A failed current-user query has no error");
  return <>{children}</>;
}

/** `FR-006`: a Sales user on an Admin route sees Not allowed, naming Admin. */
export function RequireAdmin({ children }: { children: ReactNode }): ReactElement | null {
  const { data: user, isPending } = useCurrentUser();

  if (isPending) {
    return null;
  }
  if (user?.role !== "ADMIN") {
    return <NotAllowed requiredRole="Admin" />;
  }
  return <>{children}</>;
}
