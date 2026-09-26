/**
 * `FR-004`: the user card at the foot of the navigation shows the user's display name and role
 * and offers Sign out.
 */
import { SignOutIcon } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";

import { useLogout } from "../api/auth";
import { Button } from "../components/Button";
import { titleCaseEnum } from "./formatting";
import { useCurrentUser } from "./current-user-context";

export function UserCard() {
  const user = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();

  const handleSignOut = () => {
    logout.mutate(undefined, {
      onSuccess: () => {
        void navigate("/login", { replace: true });
      },
    });
  };

  return (
    <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-text">{user.display_name}</p>
        <p className="text-[12.5px] text-text-tertiary">{titleCaseEnum(user.role)}</p>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="small"
        aria-label="Sign out"
        title="Sign out"
        onClick={handleSignOut}
        disabled={logout.isPending}
      >
        <SignOutIcon size={18} aria-hidden="true" />
      </Button>
    </div>
  );
}
