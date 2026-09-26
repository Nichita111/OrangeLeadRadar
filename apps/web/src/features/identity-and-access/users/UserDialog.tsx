import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState, type FormEvent, type ReactElement } from "react";

import { useCreateUser, useUpdateUser } from "../../../api/authenticationAndUsers";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Select, Input } from "../../../components/controls";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { useToast } from "../../../components/Toast";
import { enumLabel } from "../../../shell/format";
import { formErrors } from "../../../shell/formErrors";
import { ROLES, type Role } from "./roles";

const FIELDS = ["email", "display_name", "role", "password"] as const;

const NEW_DESCRIPTION =
  "The person can sign in with this email and password once you create the user; the email cannot be changed later.";
const EDIT_DESCRIPTION =
  "Only the fields you change are saved; the email and everything you leave as it is stay the same.";

interface UserDialogProps {
  trigger: ReactElement;
  /** Absent in New mode; the user being edited in Edit mode. */
  user?: Schemas["User"];
  /** The signed-in Admin's own row has no role field (FR-097). */
  isSelf?: boolean;
}

/** FR-096: New user and Edit share one form; Edit sends only the fields that changed. */
export function UserDialog({ trigger, user, isSelf = false }: UserDialogProps) {
  const [open, setOpen] = useState(false);
  const editing = user !== undefined;
  return (
    <Dialog
      trigger={trigger}
      title={editing ? "Edit user" : "New user"}
      description={editing ? EDIT_DESCRIPTION : NEW_DESCRIPTION}
      open={open}
      onOpenChange={setOpen}
    >
      <UserForm
        {...(user === undefined ? {} : { user })}
        isSelf={isSelf}
        onDone={() => {
          setOpen(false);
        }}
      />
    </Dialog>
  );
}

function UserForm({
  user,
  isSelf,
  onDone,
}: {
  user?: Schemas["User"];
  isSelf: boolean;
  onDone: () => void;
}) {
  const { notify } = useToast();
  const create = useCreateUser();
  const update = useUpdateUser();
  const [email, setEmail] = useState(user?.email ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [role, setRole] = useState<Role>(user?.role ?? "SALES");
  const [password, setPassword] = useState("");
  const errors = formErrors(user === undefined ? create.error : update.error, FIELDS);
  const pending = create.isPending || update.isPending;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (user === undefined) {
      create.mutate(
        { email, display_name: displayName, role, password },
        {
          onSuccess: () => {
            notify("User created");
            onDone();
          },
        },
      );
      return;
    }
    const body: Schemas["UserUpdate"] = {
      ...(displayName !== user.display_name && { display_name: displayName }),
      ...(!isSelf && role !== user.role && { role }),
      ...(password !== "" && { password }),
    };
    if (Object.keys(body).length === 0) {
      onDone();
      return;
    }
    update.mutate(
      { id: user.id, body },
      {
        onSuccess: () => {
          notify("User updated");
          onDone();
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField label="Email" error={errors.fields["email"]}>
        {(field) => (
          <Input
            {...field}
            type="email"
            autoComplete="off"
            readOnly={user !== undefined}
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        )}
      </FormField>
      <FormField label="Display name" error={errors.fields["display_name"]}>
        {(field) => (
          <Input
            {...field}
            type="text"
            autoComplete="off"
            value={displayName}
            onChange={(event) => {
              setDisplayName(event.target.value);
            }}
          />
        )}
      </FormField>
      {!isSelf && (
        <FormField label="Role" error={errors.fields["role"]}>
          {(field) => (
            <Select
              {...field}
              value={role}
              onChange={(event) => {
                setRole(ROLES.find((option) => option === event.target.value) ?? role);
              }}
            >
              {ROLES.map((option) => (
                <option key={option} value={option}>
                  {enumLabel(option)}
                </option>
              ))}
            </Select>
          )}
        </FormField>
      )}
      <FormField
        label="Password"
        {...(user === undefined ? {} : { hint: "Leave empty to keep the current password." })}
        error={errors.fields["password"]}
      >
        {(field) => (
          <Input
            {...field}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        )}
      </FormField>
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex justify-end gap-2">
        <DialogPrimitive.Close asChild>
          <Button type="button" variant="secondary">
            Cancel
          </Button>
        </DialogPrimitive.Close>
        <Button type="submit" variant="primary" disabled={pending}>
          {user === undefined ? "Create user" : "Save"}
        </Button>
      </div>
    </form>
  );
}
