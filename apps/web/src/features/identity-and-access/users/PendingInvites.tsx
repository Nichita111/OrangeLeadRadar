import { useInvites, useRevokeInvite } from "../../../api/authenticationAndUsers";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { enumLabel } from "../../../shell/format";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";

const COLUMNS = ["Email", "Role", "Invited by", "Expires", "Actions"];

/** FR-175: the pending invites, each with Revoke. Shown only while there is one. */
export function PendingInvites() {
  const invites = useInvites();
  const revoke = useRevokeInvite();
  const { notify } = useToast();
  if (invites.data?.length === 0) {
    return null;
  }
  return (
    <section className="mt-8 flex flex-col gap-3" aria-labelledby="pending-invites">
      <h2 id="pending-invites" className="m-0 text-section font-semibold">
        Pending invites
      </h2>
      {revoke.isError && <Callout kind="error">{revoke.error.message}</Callout>}
      <DataView
        query={invites}
        isEmpty={() => false}
        skeleton={<Skeleton className="h-12 w-full" />}
        empty={{ message: "No pending invites.", action: null }}
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
                {rows.map((invite) => (
                  <tr key={invite.id} className="border-b border-border last:border-b-0">
                    <td className="num px-4 py-3 text-hint text-text-secondary">{invite.email}</td>
                    <td className="px-4 py-3">{enumLabel(invite.role)}</td>
                    <td className="px-4 py-3">{invite.invited_by}</td>
                    <td className="px-4 py-3 text-text-secondary">
                      <RelativeTime at={invite.expires_at} />
                    </td>
                    <td className="px-4 py-3">
                      <ConfirmDialog
                        trigger={
                          <Button variant="ghost" size="small">
                            Revoke
                          </Button>
                        }
                        title="Revoke invite"
                        description={`The link sent to ${invite.email} will stop working at once; you can invite them again later.`}
                        confirmLabel="Revoke invite"
                        onConfirm={() => {
                          revoke.mutate(invite.id, {
                            onSuccess: () => {
                              notify("Invite revoked");
                            },
                          });
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataView>
    </section>
  );
}
