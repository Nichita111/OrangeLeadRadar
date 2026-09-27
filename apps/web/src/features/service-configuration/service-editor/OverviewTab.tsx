import { useState, type FormEvent } from "react";

import { useUpdateService } from "../../../api/servicesAndQuestions";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";
import { Textarea } from "../../../components/Textarea";
import { useToast } from "../../../components/Toast";
import { formErrors } from "../../../shell/formErrors";

const FIELDS = ["name", "description", "value_proposition"] as const;

/** FR-021: edits name, description and value proposition; the code is read-only. */
export function OverviewTab({ service }: { service: Schemas["Service"] }) {
  const [name, setName] = useState(service.name);
  const [description, setDescription] = useState(service.description);
  const [valueProposition, setValueProposition] = useState(service.value_proposition);
  const update = useUpdateService();
  const { notify } = useToast();
  const errors = formErrors(update.error, FIELDS);

  function submit(event: FormEvent) {
    event.preventDefault();
    const body: Schemas["ServiceUpdate"] = {
      ...(name !== service.name && { name }),
      ...(description !== service.description && { description }),
      ...(valueProposition !== service.value_proposition && {
        value_proposition: valueProposition,
      }),
    };
    if (Object.keys(body).length === 0) {
      return;
    }
    update.mutate(
      { id: service.id, body },
      {
        onSuccess: () => {
          notify("Service updated");
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex max-w-xl flex-col gap-4">
      <FormField label="Code">{() => <p className="num m-0">{service.code}</p>}</FormField>
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
      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={update.isPending}>
          Save
        </Button>
      </div>
    </form>
  );
}
