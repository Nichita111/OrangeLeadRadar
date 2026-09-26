/**
 * The router's outermost signed-in layout: resolves `/auth/me`, sends an anonymous visitor to
 * Sign in with the current route as return path (`FR-006`), and registers the handler
 * `client.ts` calls on a `401` from any later call, so a session that expires mid-use lands back
 * on Sign in the same way.
 */
import { useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useMe } from "../api/auth";
import { setUnauthorizedHandler } from "../api/client";
import { AppShell } from "./AppShell";
import { CurrentUserProvider } from "./current-user-context";

export function RequireAuth() {
  const { data: user, isLoading } = useMe();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      void navigate("/login", { state: { from: location }, replace: true });
    });
    return () => {
      setUnauthorizedHandler(null);
    };
  }, [navigate, location]);

  if (isLoading) {
    return <div className="h-screen bg-page" />;
  }

  if (user === null || user === undefined) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <CurrentUserProvider user={user}>
      <AppShell />
    </CurrentUserProvider>
  );
}
