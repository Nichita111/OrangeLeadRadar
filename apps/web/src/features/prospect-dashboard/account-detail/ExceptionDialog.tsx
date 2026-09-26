import { useState, type FormEvent, type ReactElement } from "react";

import { useAddOverride } from "../../../api/prospectsAndEvidence";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { Input } from "../../../components/controls";
import { FormField } from "../../../components/FormField";

/**
 * Add exception (FR-071, FR-007, FR-119): a required note; a `409` or `422` shows the api's
 * message in the dialog and keeps the input.
 */
export function ExceptionDialog({
  trigger,
  rule,
  accountId,
  serviceId,
  onAdded,
}: {
  trigger: ReactElement;
  rule: { key: string; label: string };
  accountId: string;
  serviceId: string;
  onAdded: () => void;
}) {
  const add = useAddOverride();
  const [open, setOpen] = useState(false);
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
          setOpen(false);
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={trigger}
      title="Add exception"
      description={`The rule ${rule.label} stops applying to this account for this service, and the account is rescored. The rule stays in force for every other account.`}
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {add.isError && <Callout kind="error">{add.error.message}</Callout>}
        <FormField label="Note" error={noteError}>
          {(field) => (
            <Input
              {...field}
              value={note}
              onChange={(event) => {
                setNote(event.target.value);
              }}
            />
          )}
        </FormField>
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setOpen(false);
            }}
          >
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
