import { createContext, useContext, type ReactNode } from "react";

import type { Schemas } from "../api/contract";

const CurrentUserContext = createContext<Schemas["AuthenticatedUser"] | null>(null);

export function CurrentUserProvider({
  user,
  children,
}: {
  user: Schemas["AuthenticatedUser"];
  children: ReactNode;
}) {
  return <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>;
}

/** The signed-in user; only components under `RequireSession` call it. */
export function useCurrentUser(): Schemas["AuthenticatedUser"] {
  const user = useContext(CurrentUserContext);
  if (user === null) {
    throw new Error("useCurrentUser needs a signed-in session.");
  }
  return user;
}
