import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { scoringKeys, useActivateScoringConfig } from "../../../api/scoring";
import { servicesAndQuestionsKeys } from "../../../api/servicesAndQuestions";
import { isRunFinal, useActivationRescore, useRun } from "../../../api/runs";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Textarea } from "../../../components/Textarea";
import { enumLabel } from "../../../shell/format";
import { formErrors } from "../../../shell/formErrors";

interface ActivateDialogProps {
  serviceId: string;
  draftId: string;
  disabled: boolean;
  disabledReason: string | undefined;
}

/** FR-036, FR-151 (G1 b, G7): requires a change note, confirms the recompute, then shows the
 * queued `RESCORE` run's progress. */
export function ActivateDialog({
  serviceId,
  draftId,
  disabled,
  disabledReason,
}: ActivateDialogProps) {
  const [open, setOpen] = useState(false);
  const [changeNote, setChangeNote] = useState("");
  const [activated, setActivated] = useState(false);
  const activate = useActivateScoringConfig();
  const queryClient = useQueryClient();
  const rescore = useActivationRescore(serviceId, activated);
  const run = useRun(rescore.data?.id);
  const errors = formErrors(activate.error, ["change_note"]);

  useEffect(() => {
    if (run.data !== undefined && isRunFinal(run.data)) {
      void queryClient.invalidateQueries({ queryKey: scoringKeys.configs(serviceId) });
      void queryClient.invalidateQueries({ queryKey: servicesAndQuestionsKeys.services });
    }
  }, [run.data, queryClient, serviceId]);

  function reset(next: boolean) {
    setOpen(next);
    if (!next) {
      setChangeNote("");
      setActivated(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <Button
        type="button"
        variant="primary"
        disabled={disabled}
        onClick={() => {
          setOpen(true);
        }}
      >
        Activate…
      </Button>
      {disabled && disabledReason !== undefined && (
        <span className="text-hint text-text-tertiary">{disabledReason}</span>
      )}
      <Dialog
        title="Activate this draft"
        description="Every score of the service will be recomputed from stored signals."
        open={open}
        onOpenChange={reset}
      >
        {!activated ? (
          <div className="flex flex-col gap-4">
            <FormField label="Change note" error={errors.fields["change_note"]}>
              {(field) => (
                <Textarea
                  {...field}
                  value={changeNote}
                  onChange={(event) => {
                    setChangeNote(event.target.value);
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
              <Button
                type="button"
                variant="primary"
                disabled={activate.isPending || changeNote === ""}
                onClick={() => {
                  activate.mutate(
                    { id: draftId, body: { change_note: changeNote } },
                    {
                      onSuccess: () => {
                        setActivated(true);
                      },
                    },
                  );
                }}
              >
                Activate
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <Callout kind="accent">This draft is now active.</Callout>
            {rescore.data !== undefined ? (
              <p className="m-0">
                {`Rescore ${enumLabel((run.data ?? rescore.data).status).toLowerCase()}`}
                {run.data?.stage !== null &&
                  run.data?.stage !== undefined &&
                  ` — ${enumLabel(run.data.stage)}`}
                {". "}
                <Link to={`/runs?run=${rescore.data.id}`} className="underline">
                  View the run
                </Link>
                .
              </p>
            ) : (
              <p className="m-0">
                <Link to="/runs" className="underline">
                  View Runs
                </Link>
                .
              </p>
            )}
          </div>
        )}
      </Dialog>
    </span>
  );
}
