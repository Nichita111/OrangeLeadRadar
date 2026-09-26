/**
 * Add exception (`FR-071`, `FR-007`, `FR-119`): a required note; a `409` or `422` shows the api's
 * message in the dialog and keeps the input.
 */
import { useState, type FormEvent } from "react";

import { useAddOverride } from "../../../api/prospects";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { Input } from "../../../components/Input";

export function ExceptionDialog({
  rule,
  accountId,
  serviceId,
  onClose,
  onAdded,
}: {
  rule: { key: string; label: string };
  accountId: string;
  serviceId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const add = useAddOverride();
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState<string | undefined>();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (note.trim() === "") {
      setNoteError("Enter a note.");
      return;
    }
    setNoteError(undefined);
    add.mutate(
      { accountId, serviceId, body: { rule_key: rule.key, note: note.trim() } },
      {
        onSuccess: () => {
          onAdded();
          onClose();
        },
      },
    );
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      title="Add exception"
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <p className="text-sm text-text-secondary">
          The rule {rule.label} stops applying to this account for this service, and the account is
          rescored. The rule stays in force for every other account.
        </p>
        {add.error !== null && <Callout kind="error">{add.error.message}</Callout>}
        <Input
          id="exception-note"
          label="Note"
          value={note}
          error={noteError}
          onChange={(event) => {
            setNote(event.target.value);
          }}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={add.isPending}>
            Add exception
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
