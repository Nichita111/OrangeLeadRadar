import { SignOutIcon } from "@phosphor-icons/react";
import { useNavigate } from "react-router";

import { useLogout } from "../api/authenticationAndUsers";
import { IconButton } from "../components/Button";
import { Callout } from "../components/Callout";
import { enumLabel } from "./format";
import { useCurrentUser } from "./CurrentUser";

/** FR-004: the display name and role, and Sign out; a failed sign-out shows its message. */
export function UserCard() {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const logout = useLogout();
  return (
    <section
      aria-label="Signed in user"
      className="flex flex-col gap-2 rounded-card border border-border bg-surface p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-semibold">{user.display_name}</span>
          <span className="text-hint text-text-tertiary">{enumLabel(user.role)}</span>
        </div>
        <IconButton
          label="Sign out"
          icon={<SignOutIcon size={20} aria-hidden />}
          disabled={logout.isPending}
          onClick={() => {
            logout.mutate(undefined, {
              onSuccess: () => {
                void navigate("/login", { replace: true });
              },
            });
          }}
        />
      </div>
      {logout.isError && <Callout kind="error">{logout.error.message}</Callout>}
    </section>
  );
}
