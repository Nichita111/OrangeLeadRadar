/**
 * `FR-096`: New user and Edit set display name, role and, on creation or reset, a password of
 * at least `PASSWORD_MIN_LENGTH` characters; the email is fixed after creation. One dialog
 * serves both, since they share every field but the email and the reset toggle.
 * `FR-097`: the signed-in Admin's own row offers no role change, so `isSelf` hides that field.
 */
import { useState, type FormEvent } from "react";

import { useCreateUser, useUpdateUser, type AppUserRole, type User } from "../../../api/users";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { Input } from "../../../components/Input";
import { Select } from "../../../components/Select";
import { fieldErrorsOf, formLevelError } from "./field-errors";

const ROLE_OPTIONS: { value: AppUserRole; label: string }[] = [
  { value: "SALES", label: "Sales" },
  { value: "ADMIN", label: "Admin" },
];

function isAppUserRole(value: string): value is AppUserRole {
  return value === "SALES" || value === "ADMIN";
}

export interface UserFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  user?: User | undefined;
  isSelf?: boolean;
  onSaved: (message: string) => void;
}

export function UserFormDialog({
  open,
  onOpenChange,
  mode,
  user,
  isSelf = false,
  onSaved,
}: UserFormDialogProps) {
  const [email, setEmail] = useState(user?.email ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [role, setRole] = useState<AppUserRole>(user?.role ?? "SALES");
  const [resetPassword, setResetPassword] = useState(mode === "create");
  const [password, setPassword] = useState("");

  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const pending = createUser.isPending || updateUser.isPending;
  const error = createUser.error ?? updateUser.error;
  const errors = fieldErrorsOf(error);
  const topLevelError = formLevelError(error, errors);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mode === "create") {
      createUser.mutate(
        { email, display_name: displayName, role, password },
        {
          onSuccess: () => {
            onSaved(`${displayName} was added.`);
            onOpenChange(false);
          },
        },
      );
      return;
    }
    if (user === undefined) {
      return;
    }
    updateUser.mutate(
      {
        id: user.id,
        body: {
          display_name: displayName,
          ...(isSelf ? {} : { role }),
          ...(resetPassword ? { password } : {}),
        },
      },
      {
        onSuccess: () => {
          onSaved(
            resetPassword ? `${displayName}'s password was reset.` : `${displayName} was updated.`,
          );
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={mode === "create" ? "New user" : "Edit user"}
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
        {topLevelError !== null && <Callout kind="error">{topLevelError}</Callout>}
        {mode === "create" && (
          <Input
            id="user-email"
            type="email"
            label="Email"
            autoComplete="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
            error={errors.email}
            required
          />
        )}
        <Input
          id="user-display-name"
          label="Display name"
          value={displayName}
          onChange={(event) => {
            setDisplayName(event.target.value);
          }}
          error={errors.display_name}
          required
        />
        {isSelf ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-text">Role</span>
            <p className="text-sm text-text-secondary">
              {ROLE_OPTIONS.find((option) => option.value === role)?.label} (you cannot change your
              own role)
            </p>
          </div>
        ) : (
          <Select
            id="user-role"
            label="Role"
            value={role}
            onValueChange={(value) => {
              if (isAppUserRole(value)) {
                setRole(value);
              }
            }}
            options={ROLE_OPTIONS}
            error={errors.role}
          />
        )}
        {mode === "edit" && (
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={resetPassword}
              onChange={(event) => {
                setResetPassword(event.target.checked);
              }}
            />
            Reset password
          </label>
        )}
        {(mode === "create" || resetPassword) && (
          <Input
            id="user-password"
            type="password"
            label="Password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
            error={errors.password}
            required
          />
        )}
        <div className="mt-2 flex justify-end gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={pending}>
            {mode === "create" ? "Create user" : "Save"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
