import type { ReactNode } from "react";

import { useCurrentUser } from "./CurrentUser";
import { NotAllowed } from "./states/NotAllowed";

/** Admin routes are guarded in the router; the api enforces the role regardless. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const user = useCurrentUser();
  return user.role === "ADMIN" ? <>{children}</> : <NotAllowed />;
}
