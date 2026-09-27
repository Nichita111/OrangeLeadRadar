import { CopyIcon } from "@phosphor-icons/react";
import { useState, type FormEvent, type ReactElement } from "react";

import { useCreateInvite } from "../../../api/authenticationAndUsers";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Input, Select } from "../../../components/controls";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { useToast } from "../../../components/Toast";
import { enumLabel } from "../../../shell/format";
import { formErrors } from "../../../shell/formErrors";
import { ROLES, type Role } from "./roles";

const FIELDS = ["email", "role"] as const;

/** The hours an invite stays usable, read from the invite itself (`INVITE_TTL_HOURS`). */
export function inviteHours(invite: Schemas["Invite"]): number {
  return Math.round((Date.parse(invite.expires_at) - Date.parse(invite.created_at)) / 3_600_000);
}

/** FR-174: invites an email with a role and shows the link once, to copy and hand over. */
export function InviteDialog({ trigger }: { trigger: ReactElement }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog
      trigger={trigger}
      title="Invite user"
      description="The person joins by opening the link you send them and choosing their own password."
      open={open}
      onOpenChange={setOpen}
    >
      {/* A fresh form each time the dialog opens, so a shown link never reappears. */}
      {open && (
        <InviteForm
          onDone={() => {
            setOpen(false);
          }}
        />
      )}
    </Dialog>
  );
}

function InviteForm({ onDone }: { onDone: () => void }) {
  const create = useCreateInvite();
  const { notify } = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("SALES");
  const errors = formErrors(create.error, FIELDS);

  if (create.data !== undefined) {
    const { invite, link } = create.data;
    return (
      <div className="flex flex-col gap-4">
        <FormField label={`Invite link for ${invite.email}`}>
          {(field) => <Input {...field} readOnly value={link} className="num" />}
        </FormField>
        <p className="m-0 text-text-secondary">
          Send this link yourself; LeadRadar sends no message. It works once, for{" "}
          {inviteHours(invite)} hours.
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              void navigator.clipboard.writeText(link).then(() => {
                notify("Link copied");
              });
            }}
          >
            <CopyIcon size={16} aria-hidden />
            Copy link
          </Button>
          <Button variant="primary" onClick={onDone}>
            Done
          </Button>
        </div>
      </div>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({ email, role });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField label="Email" error={errors.fields["email"]}>
        {(field) => (
          <Input
            {...field}
            type="email"
            autoComplete="off"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        )}
      </FormField>
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
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={create.isPending}>
          Create invite link
        </Button>
      </div>
    </form>
  );
}
