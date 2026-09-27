import { useState } from "react";

import { useAcceptCandidate, type DiscoveryCandidate } from "../../../api/discovery";
import { ApiError } from "../../../api/client";
import { Button } from "../../../components/Button";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";
import { formErrors } from "../../../shell/formErrors";

interface AcceptCandidateDialogProps {
  candidate: DiscoveryCandidate;
  serviceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** FR-052, FR-007: asks for the domain when the candidate has none; a `422` keeps the input with
 * its field error, a `409` links to the conflicting account. */
export function AcceptCandidateDialog({
  candidate,
  serviceId,
  open,
  onOpenChange,
}: AcceptCandidateDialogProps) {
  const [domain, setDomain] = useState("");
  const accept = useAcceptCandidate(serviceId);
  const errors = formErrors(accept.error, ["domain"]);
  const conflictId =
    accept.error instanceof ApiError && accept.error.envelope.error.code === "CONFLICT"
      ? accept.error.envelope.error.details?.entity_id
      : undefined;

  async function handleSubmit() {
    try {
      await accept.mutateAsync({ id: candidate.id, domain });
      onOpenChange(false);
      setDomain("");
    } catch {
      // The error is shown below the field or as a conflict link; the dialog stays open.
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Accept candidate"
      description={`Enter ${candidate.name}'s website to create its account and queue its refresh.`}
    >
      <FormField label="Website domain" error={errors.fields["domain"]}>
        {(field) => (
          <Input
            {...field}
            value={domain}
            onChange={(event) => {
              setDomain(event.target.value);
            }}
            placeholder="example.com"
          />
        )}
      </FormField>
      {conflictId !== undefined && (
        <p className="m-0 text-negative">
          That domain is already an account.{" "}
          <a className="underline" href={`/accounts/${conflictId}`}>
            Open it
          </a>
          .
        </p>
      )}
      {errors.callout !== undefined && <p className="m-0 text-negative">{errors.callout}</p>}
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={domain.trim() === "" || accept.isPending}
          onClick={() => void handleSubmit()}
        >
          Accept
        </Button>
      </div>
    </Dialog>
  );
}
