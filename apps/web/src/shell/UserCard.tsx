import type { ReactElement } from "react";
import { useNavigate } from "react-router";

import { useSignOut } from "../api/auth";
import type { components } from "../api/schema.gen";
import { Button } from "../components/ui/button";

type User = components["schemas"]["AuthenticatedUser"];

export function UserCard({ user }: { user: User }): ReactElement {
  const signOut = useSignOut();
  const navigate = useNavigate();
  return (
    <div className="rounded-card border border-border p-3">
      <p className="font-medium text-text">{user.display_name}</p>
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="text-sm text-text-secondary">
          {user.role === "ADMIN" ? "Admin" : "Sales"}
        </span>
        <Button
          variant="ghost"
          onClick={() => {
            signOut.mutate(undefined, {
              onSuccess: () => {
                void navigate("/login");
              },
            });
          }}
        >
          Sign out
        </Button>
      </div>
    </div>
  );
}
