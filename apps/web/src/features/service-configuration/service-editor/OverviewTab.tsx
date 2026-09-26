/**
 * `FR-021`: edits name, description and value proposition; the code is read-only.
 */
import { useState, type FormEvent } from "react";

import { useUpdateService, type Service } from "../../../api/services";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Input } from "../../../components/Input";
import { Textarea } from "../../../components/Textarea";
import { useToast } from "../../../components/Toast";
import { fieldErrorsOf, formLevelError } from "../../identity-and-access/users/field-errors";

export function OverviewTab({ service }: { service: Service }) {
  const [name, setName] = useState(service.name);
  const [description, setDescription] = useState(service.description);
  const [valueProposition, setValueProposition] = useState(service.value_proposition);

  const updateService = useUpdateService();
  const { showToast } = useToast();
  const errors = fieldErrorsOf(updateService.error);
  const topLevelError = formLevelError(updateService.error, errors);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    updateService.mutate(
      {
        id: service.id,
        body: { name, description, value_proposition: valueProposition },
      },
      {
        onSuccess: () => {
          showToast("Service was updated.");
        },
      },
    );
  };

  return (
    <form className="flex max-w-xl flex-col gap-4" onSubmit={handleSubmit} noValidate>
      {topLevelError !== null && <Callout kind="error">{topLevelError}</Callout>}
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-text">Code</span>
        <span className="font-mono text-sm text-text-secondary">{service.code}</span>
      </div>
      <Input
        id="overview-name"
        label="Name"
        value={name}
        onChange={(event) => {
          setName(event.target.value);
        }}
        error={errors.name}
        required
      />
      <Textarea
        id="overview-description"
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
        id="overview-value-proposition"
        label="Value proposition"
        hint="What the service offers a prospect."
        value={valueProposition}
        onChange={(event) => {
          setValueProposition(event.target.value);
        }}
        error={errors.value_proposition}
        required
      />
      <div className="mt-2 flex justify-end">
        <Button type="submit" variant="primary" disabled={updateService.isPending}>
          Save
        </Button>
      </div>
    </form>
  );
}
