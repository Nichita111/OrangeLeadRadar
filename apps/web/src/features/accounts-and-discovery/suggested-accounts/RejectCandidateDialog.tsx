import { useState } from "react";

import { useRejectCandidate, type DiscoveryCandidate } from "../../../api/discovery";
import { Button } from "../../../components/Button";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Textarea } from "../../../components/Textarea";

interface RejectCandidateDialogProps {
  candidate: DiscoveryCandidate;
  serviceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** FR-053: an optional reason; the candidate leaves the Pending list for good. */
export function RejectCandidateDialog({
  candidate,
  serviceId,
  open,
  onOpenChange,
}: RejectCandidateDialogProps) {
  const [reason, setReason] = useState("");
  const reject = useRejectCandidate(serviceId);

  async function handleSubmit() {
    const trimmed = reason.trim();
    await reject.mutateAsync({ id: candidate.id, ...(trimmed === "" ? {} : { reason: trimmed }) });
    onOpenChange(false);
    setReason("");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Reject candidate"
      description={`${candidate.name} will not be suggested again for this service.`}
    >
      <FormField label="Reason (optional)">
        {(field) => (
          <Textarea
            {...field}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
            }}
          />
        )}
      </FormField>
      {reject.error !== null && <p className="m-0 text-negative">{reject.error.message}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button variant="primary" disabled={reject.isPending} onClick={() => void handleSubmit()}>
          Reject
        </Button>
      </div>
    </Dialog>
  );
}
