import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState, type FormEvent, type ReactElement } from "react";

import { useCreateService } from "../../../api/servicesAndQuestions";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";
import { Textarea } from "../../../components/Textarea";
import { useToast } from "../../../components/Toast";
import { formErrors } from "../../../shell/formErrors";
import { toUpperSnakeInput } from "../../../shell/upperSnake";

const FIELDS = ["code", "name", "description", "value_proposition"] as const;

/**
 * `FR-019`: New service opens a dialog with code, name, description and value proposition; the
 * code accepts UPPER_SNAKE only and cannot be changed later.
 */
export function NewServiceDialog({ trigger }: { trigger: ReactElement }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog
      trigger={trigger}
      title="New service"
      description="The code accepts UPPER_SNAKE only and cannot be changed later."
      open={open}
      onOpenChange={setOpen}
    >
      <NewServiceForm
        onDone={() => {
          setOpen(false);
        }}
      />
    </Dialog>
  );
}

function NewServiceForm({ onDone }: { onDone: () => void }) {
  const { notify } = useToast();
  const create = useCreateService();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [valueProposition, setValueProposition] = useState("");
  const errors = formErrors(create.error, FIELDS);

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate(
      { code, name, description, value_proposition: valueProposition },
      {
        onSuccess: (service) => {
          notify(`${service.name} created`);
          onDone();
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField label="Code" hint="Cannot be changed later." error={errors.fields["code"]}>
        {(field) => (
          <Input
            {...field}
            type="text"
            value={code}
            onChange={(event) => {
              setCode(toUpperSnakeInput(event.target.value));
            }}
          />
        )}
      </FormField>
      <FormField label="Name" error={errors.fields["name"]}>
        {(field) => (
          <Input
            {...field}
            type="text"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        )}
      </FormField>
      <FormField label="Description" error={errors.fields["description"]}>
        {(field) => (
          <Textarea
            {...field}
            value={description}
            onChange={(event) => {
              setDescription(event.target.value);
            }}
          />
        )}
      </FormField>
      <FormField label="Value proposition" error={errors.fields["value_proposition"]}>
        {(field) => (
          <Textarea
            {...field}
            value={valueProposition}
            onChange={(event) => {
              setValueProposition(event.target.value);
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
        <Button type="submit" variant="primary" disabled={create.isPending}>
          Create service
        </Button>
      </div>
    </form>
  );
}
