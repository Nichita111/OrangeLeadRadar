import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState, type FormEvent, type ReactElement } from "react";

import { useCreateIndustry, useUpdateIndustry } from "../../../api/industriesAndMarkets";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";
import { useToast } from "../../../components/Toast";
import { formErrors } from "../../../shell/formErrors";
import { toUpperSnakeInput } from "../../../shell/upperSnake";

const FIELDS = ["code", "label"] as const;

interface IndustryDialogProps {
  /** Omitted when a `RowMenu` item opens the dialog under fully controlled `open` instead. */
  trigger?: ReactElement;
  /** Absent in New mode; the industry being renamed in Rename mode. */
  industry?: Schemas["Industry"];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/** FR-155, FR-156: New industry and Rename share one form; the code cannot change once set. */
export function IndustryDialog({ trigger, industry, open, onOpenChange }: IndustryDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const currentOpen = open ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;
  const editing = industry !== undefined;
  return (
    <Dialog
      {...(trigger === undefined ? {} : { trigger })}
      title={editing ? "Rename industry" : "New industry"}
      description={
        editing
          ? "Only the label changes; the code stays the same."
          : "The code accepts UPPER_SNAKE only and cannot be changed later."
      }
      open={currentOpen}
      onOpenChange={setOpen}
    >
      <IndustryForm
        {...(industry === undefined ? {} : { industry })}
        onDone={() => {
          setOpen(false);
        }}
      />
    </Dialog>
  );
}

function IndustryForm({
  industry,
  onDone,
}: {
  industry?: Schemas["Industry"];
  onDone: () => void;
}) {
  const { notify } = useToast();
  const create = useCreateIndustry();
  const update = useUpdateIndustry();
  const [code, setCode] = useState(industry?.code ?? "");
  const [label, setLabel] = useState(industry?.label ?? "");
  const errors = formErrors(industry === undefined ? create.error : update.error, FIELDS);
  const pending = create.isPending || update.isPending;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (industry === undefined) {
      create.mutate(
        { code, label },
        {
          onSuccess: () => {
            notify("Industry created");
            onDone();
          },
        },
      );
      return;
    }
    if (label === industry.label) {
      onDone();
      return;
    }
    update.mutate(
      { code: industry.code, body: { label } },
      {
        onSuccess: () => {
          notify("Industry renamed");
          onDone();
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField
        label="Code"
        hint={industry === undefined ? "Cannot be changed later." : undefined}
        error={errors.fields["code"]}
      >
        {(field) => (
          <Input
            {...field}
            type="text"
            readOnly={industry !== undefined}
            value={code}
            onChange={(event) => {
              setCode(toUpperSnakeInput(event.target.value));
            }}
          />
        )}
      </FormField>
      <FormField label="Label" error={errors.fields["label"]}>
        {(field) => (
          <Input
            {...field}
            type="text"
            value={label}
            onChange={(event) => {
              setLabel(event.target.value);
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
          {industry === undefined ? "Create industry" : "Save"}
        </Button>
      </div>
    </form>
  );
}
