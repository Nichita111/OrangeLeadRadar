/**
 * [Users](/features/identity-and-access.md#users). Route `/users`, Admin only. WF-22.
 */
import { ArrowCounterClockwiseIcon, PencilSimpleIcon, ProhibitIcon } from "@phosphor-icons/react";
import { useState } from "react";

import { useUpdateUser, useUsers, type User } from "../../../api/users";
import { Button } from "../../../components/Button";
import { Chip } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/Dialog";
import { EmptyState, QueryErrorState, SkeletonRows } from "../../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../../components/Table";
import { useToast } from "../../../components/Toast";
import { useCurrentUser } from "../../../shell/current-user-context";
import { formatAbsoluteDateTime, formatLastLogin, titleCaseEnum } from "../../../shell/formatting";
import { UserFormDialog } from "./UserFormDialog";

const COLUMN_COUNT = 6;

type FormDialogState = { mode: "create" } | { mode: "edit"; user: User } | null;

export function UsersScreen() {
  const { data: users, isLoading, isError, error, refetch } = useUsers();
  const currentUser = useCurrentUser();
  const { showToast } = useToast();
  const updateUser = useUpdateUser();

  const [formDialog, setFormDialog] = useState<FormDialogState>(null);
  const [disableTarget, setDisableTarget] = useState<User | null>(null);

  const handleEnable = (user: User) => {
    updateUser.mutate(
      { id: user.id, body: { status: "ACTIVE" } },
      {
        onSuccess: () => {
          showToast(`${user.display_name} was re-enabled.`);
        },
      },
    );
  };

  const handleConfirmDisable = () => {
    if (disableTarget === null) {
      return;
    }
    updateUser.mutate(
      { id: disableTarget.id, body: { status: "DISABLED" } },
      {
        onSuccess: () => {
          showToast(`${disableTarget.display_name} was disabled.`);
          setDisableTarget(null);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-text">Users</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Create accounts for your team, and manage their role, status and password.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => {
            setFormDialog({ mode: "create" });
          }}
        >
          New user
        </Button>
      </div>

      <Table caption="Users">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Email</TableHeaderCell>
            <TableHeaderCell>Role</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Last sign-in</TableHeaderCell>
            <TableHeaderCell>
              <span className="sr-only">Actions</span>
            </TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading && <SkeletonRows rows={3} columns={COLUMN_COUNT} />}
          {!isLoading && isError && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <QueryErrorState error={error} onRetry={() => void refetch()} />
              </TableCell>
            </TableRow>
          )}
          {!isLoading && !isError && users !== undefined && users.length === 0 && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <EmptyState
                  message="No users yet. Create the first account for your team."
                  actionLabel="New user"
                  onAction={() => {
                    setFormDialog({ mode: "create" });
                  }}
                />
              </TableCell>
            </TableRow>
          )}
          {!isLoading &&
            !isError &&
            users !== undefined &&
            users.map((user) => {
              const isSelf = user.id === currentUser.id;
              return (
                <TableRow key={user.id}>
                  <TableCell>{user.display_name}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{titleCaseEnum(user.role)}</TableCell>
                  <TableCell>
                    <Chip tone={user.status === "ACTIVE" ? "positive" : "neutral"}>
                      {titleCaseEnum(user.status)}
                    </Chip>
                  </TableCell>
                  <TableCell>
                    <span
                      title={
                        user.last_login_at !== null
                          ? formatAbsoluteDateTime(user.last_login_at)
                          : undefined
                      }
                    >
                      {formatLastLogin(user.last_login_at)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="small"
                        aria-label={`Edit ${user.display_name}`}
                        title="Edit"
                        onClick={() => {
                          setFormDialog({ mode: "edit", user });
                        }}
                      >
                        <PencilSimpleIcon size={16} aria-hidden="true" />
                      </Button>
                      {!isSelf && user.status === "ACTIVE" && (
                        <Button
                          variant="ghost"
                          size="small"
                          aria-label={`Disable ${user.display_name}`}
                          title="Disable"
                          onClick={() => {
                            setDisableTarget(user);
                          }}
                        >
                          <ProhibitIcon size={16} aria-hidden="true" />
                        </Button>
                      )}
                      {!isSelf && user.status === "DISABLED" && (
                        <Button
                          variant="ghost"
                          size="small"
                          aria-label={`Re-enable ${user.display_name}`}
                          title="Re-enable"
                          onClick={() => {
                            handleEnable(user);
                          }}
                        >
                          <ArrowCounterClockwiseIcon size={16} aria-hidden="true" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
        </TableBody>
      </Table>

      {formDialog !== null && (
        <UserFormDialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setFormDialog(null);
            }
          }}
          mode={formDialog.mode}
          user={formDialog.mode === "edit" ? formDialog.user : undefined}
          isSelf={formDialog.mode === "edit" && formDialog.user.id === currentUser.id}
          onSaved={showToast}
        />
      )}

      <ConfirmDialog
        open={disableTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDisableTarget(null);
          }
        }}
        title="Disable user"
        description={
          <>
            {disableTarget?.display_name} will be signed out everywhere and will not be able to sign
            in again until re-enabled. Their history is kept.
          </>
        }
        confirmLabel="Disable user"
        onConfirm={handleConfirmDisable}
        confirmPending={updateUser.isPending}
      />
    </div>
  );
}
