import { PlusIcon } from "@phosphor-icons/react";

import { useUpdateUser, useUsers } from "../../../api/authenticationAndUsers";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { useCurrentUser } from "../../../shell/CurrentUser";
import { enumLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { UserDialog } from "./UserDialog";

const COLUMNS = ["Name", "Email", "Role", "Status", "Last sign-in", "Actions"];

function SkeletonRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-12 w-full" />
      ))}
    </div>
  );
}

/** FL-20, FR-095 to FR-097, FR-158: the Admin's list of users and what can be done to each. */
export function Users() {
  const users = useUsers();
  const me = useCurrentUser();
  const update = useUpdateUser();
  const { notify } = useToast();

  function setStatus(user: Schemas["User"], status: Schemas["User"]["status"], toast: string) {
    update.mutate(
      { id: user.id, body: { status } },
      {
        onSuccess: () => {
          notify(toast);
        },
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Users"
        lead="Create the people who can sign in, choose their role, and disable anyone who should no longer have access."
        action={
          <UserDialog
            trigger={
              <Button variant="primary">
                <PlusIcon size={16} aria-hidden />
                New user
              </Button>
            }
          />
        }
      />
      {update.isError && <Callout kind="error">{update.error.message}</Callout>}
      <DataView
        query={users}
        isEmpty={(rows) => rows.length === 0}
        skeleton={<SkeletonRows />}
        empty={{
          message: "No users yet. New user creates the first one.",
          action: <UserDialog trigger={<Button variant="secondary">New user</Button>} />,
        }}
      >
        {(rows) => (
          <div className="overflow-hidden rounded-card border border-border bg-surface">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  {COLUMNS.map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((user) => {
                  const isSelf = user.id === me.id;
                  return (
                    <tr key={user.id} className="border-b border-border last:border-b-0">
                      <td className="px-4 py-3 font-medium">
                        {user.display_name}
                        {isSelf && <span className="ml-2 text-hint text-text-tertiary">You</span>}
                      </td>
                      <td className="num px-4 py-3 text-hint text-text-secondary">{user.email}</td>
                      <td className="px-4 py-3">{enumLabel(user.role)}</td>
                      <td className="px-4 py-3">
                        <Chip tone={user.status === "ACTIVE" ? "positive" : "neutral"}>
                          {enumLabel(user.status)}
                        </Chip>
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {user.last_login_at === null ? (
                          "Never"
                        ) : (
                          <RelativeTime at={user.last_login_at} />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <UserDialog
                            user={user}
                            isSelf={isSelf}
                            trigger={
                              <Button variant="secondary" size="small">
                                Edit
                              </Button>
                            }
                          />
                          {!isSelf && user.status === "ACTIVE" && (
                            <ConfirmDialog
                              trigger={
                                <Button variant="ghost" size="small">
                                  Disable
                                </Button>
                              }
                              title="Disable user"
                              description={`${user.display_name} will be signed out everywhere and cannot sign in until an Admin enables them again; their feedback, labels and audit history are kept.`}
                              confirmLabel="Disable user"
                              onConfirm={() => {
                                setStatus(user, "DISABLED", "User disabled");
                              }}
                            />
                          )}
                          {user.status === "DISABLED" && (
                            <Button
                              variant="ghost"
                              size="small"
                              onClick={() => {
                                setStatus(user, "ACTIVE", "User enabled");
                              }}
                            >
                              Enable
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </DataView>
    </>
  );
}
