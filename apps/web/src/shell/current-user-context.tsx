/**
 * The signed-in user, made available to the shell and every screen inside it without a second
 * `/auth/me` call.
 */
import { createContext, useContext, type ReactNode } from "react";

import type { AuthenticatedUser } from "../api/auth";

const CurrentUserContext = createContext<AuthenticatedUser | null>(null);

export function CurrentUserProvider({
  user,
  children,
}: {
  user: AuthenticatedUser;
  children: ReactNode;
}) {
  return <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>;
}

/** Only rendered inside `RequireAuth`, so the user is always set. */
export function useCurrentUser(): AuthenticatedUser {
  const user = useContext(CurrentUserContext);
  if (user === null) {
    throw new Error("useCurrentUser must be used within a signed-in route");
  }
  return user;
}
