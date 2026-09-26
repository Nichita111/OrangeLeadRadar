/**
 * `FR-019`: New service opens a dialog with code, name, description and value proposition; the
 * code field accepts UPPER_SNAKE only and explains that it cannot be changed later. Editing an
 * existing service is [Overview](/features/service-configuration.md#service-editor) (`FR-021`),
 * not this dialog.
 */
import { useState, type FormEvent } from "react";

import { useCreateService } from "../../../api/services";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Dialog } from "../../../components/Dialog";
import { Input } from "../../../components/Input";
import { Textarea } from "../../../components/Textarea";
import { fieldErrorsOf, formLevelError } from "../../identity-and-access/users/field-errors";

export interface NewServiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (message: string) => void;
}

export function NewServiceDialog({ open, onOpenChange, onCreated }: NewServiceDialogProps) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [valueProposition, setValueProposition] = useState("");

  const createService = useCreateService();
  const errors = fieldErrorsOf(createService.error);
  const topLevelError = formLevelError(createService.error, errors);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    createService.mutate(
      { code, name, description, value_proposition: valueProposition },
      {
        onSuccess: () => {
          onCreated(`${name} was created.`);
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New service">
      <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
        {topLevelError !== null && <Callout kind="error">{topLevelError}</Callout>}
        <Input
          id="service-code"
          label="Code"
          hint="UPPER_SNAKE, e.g. INTELLIGENT_AUTOMATION. Cannot be changed later."
          value={code}
          onChange={(event) => {
            setCode(event.target.value.toUpperCase());
          }}
          error={errors.code}
          required
        />
        <Input
          id="service-name"
          label="Name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
          error={errors.name}
          required
        />
        <Textarea
          id="service-description"
          label="Description"
          hint="What the service delivers, in two or three sentences."
          value={description}
          onChange={(event) => {
            setDescription(event.target.value);
          }}
          error={errors.description}
          required
        />
        <Textarea
          id="service-value-proposition"
          label="Value proposition"
          hint="What the service offers a prospect."
          value={valueProposition}
          onChange={(event) => {
            setValueProposition(event.target.value);
          }}
          error={errors.value_proposition}
          required
        />
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
          <Button type="submit" variant="primary" disabled={createService.isPending}>
            Create service
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
