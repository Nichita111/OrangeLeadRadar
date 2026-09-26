/** Guards the Admin routes of the router ([TypeScript guidelines]
 * (/guidelines/typescript.md#routing)); the api enforces the role regardless. */
import { Outlet } from "react-router-dom";

import { useCurrentUser } from "./current-user-context";
import { NotAllowed } from "./NotAllowed";

export function RequireAdmin() {
  const user = useCurrentUser();
  if (user.role !== "ADMIN") {
    return <NotAllowed requiredRole="Admin" />;
  }
  return <Outlet />;
}
