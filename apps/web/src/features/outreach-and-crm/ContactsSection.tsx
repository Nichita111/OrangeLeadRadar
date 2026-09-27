import { useState, type FormEvent } from "react";

import {
  CONTACT_PERSONAS,
  useContactMutations,
  useContacts,
  type Contact,
  type ContactPersona,
} from "../../api/contactsAndOutreach";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { FormField } from "../../components/FormField";
import { Input, Select } from "../../components/controls";
import { Skeleton } from "../../components/Skeleton";
import { enumLabel } from "../../shell/format";
import { formErrors } from "../../shell/formErrors";
import { DataView } from "../../shell/states/DataView";

const FORM_FIELDS = ["full_name", "job_title", "source_url", "persona"] as const;

interface ContactFormValues {
  full_name: string;
  job_title: string;
  source_url: string;
  persona: ContactPersona | "";
}

const EMPTY: ContactFormValues = { full_name: "", job_title: "", source_url: "", persona: "" };

/**
 * FR-048, FR-049: an account's contacts with name, job title, persona and its origin, and the
 * source page. Add and Edit take no email address or phone number; the persona is suggested from
 * the job title when left empty.
 */
export function ContactsSection({ accountId }: { accountId: string }) {
  const contacts = useContacts(accountId);
  const { create, update, erase } = useContactMutations(accountId);
  const [editing, setEditing] = useState<string | null>(null);

  const mutation = editing === "new" ? create : update;
  const errors = formErrors(mutation.error ?? erase.error, FORM_FIELDS);

  function submit(values: ContactFormValues, contact: Contact | null) {
    const body = {
      full_name: values.full_name,
      job_title: values.job_title,
      source_url: values.source_url,
      ...(values.persona === "" ? {} : { persona: values.persona }),
    };
    const onSuccess = () => {
      setEditing(null);
    };
    if (contact === null) {
      create.mutate(body, { onSuccess });
    } else {
      update.mutate({ id: contact.id, body }, { onSuccess });
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="m-0 text-section font-semibold">Contacts</h2>
        {editing === null && (
          <Button
            size="small"
            onClick={() => {
              create.reset();
              setEditing("new");
            }}
          >
            Add contact
          </Button>
        )}
      </div>
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      {editing === "new" && (
        <ContactForm
          initial={EMPTY}
          errors={errors.fields}
          pending={create.isPending}
          onSubmit={(values) => {
            submit(values, null);
          }}
          onCancel={() => {
            setEditing(null);
          }}
        />
      )}
      <DataView
        query={contacts}
        isEmpty={(items) => items.length === 0}
        skeleton={<Skeleton className="h-16 w-full" />}
        empty={{ message: "No contacts yet.", action: null }}
      >
        {(items) => (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {items.map((contact) =>
              editing === contact.id ? (
                <li key={contact.id}>
                  <ContactForm
                    initial={{
                      full_name: contact.full_name,
                      job_title: contact.job_title,
                      source_url: contact.source_url,
                      persona: contact.persona_origin === "MANUAL" ? contact.persona : "",
                    }}
                    errors={errors.fields}
                    pending={update.isPending}
                    onSubmit={(values) => {
                      submit(values, contact);
                    }}
                    onCancel={() => {
                      setEditing(null);
                    }}
                  />
                </li>
              ) : (
                <li
                  key={contact.id}
                  className="flex items-start justify-between gap-3 rounded-control border border-border p-3"
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">{contact.full_name}</span>
                    <span className="text-text-secondary">{contact.job_title}</span>
                    <span className="text-hint text-text-tertiary">
                      {enumLabel(contact.persona)} ·{" "}
                      {contact.persona_origin === "MANUAL" ? "set by a user" : "suggested"} ·{" "}
                      <a
                        href={contact.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent-ink underline"
                      >
                        source
                      </a>
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="small"
                      variant="ghost"
                      onClick={() => {
                        update.reset();
                        setEditing(contact.id);
                      }}
                    >
                      Edit
                    </Button>
                    <ConfirmDialog
                      trigger={
                        <Button size="small" variant="ghost">
                          Erase
                        </Button>
                      }
                      title={`Erase ${contact.full_name}`}
                      description="The contact is deleted permanently; drafts addressed to them keep no name."
                      confirmLabel="Erase"
                      onConfirm={() => {
                        erase.mutate(contact.id);
                      }}
                    />
                  </div>
                </li>
              ),
            )}
          </ul>
        )}
      </DataView>
    </section>
  );
}

function ContactForm({
  initial,
  errors,
  pending,
  onSubmit,
  onCancel,
}: {
  initial: ContactFormValues;
  errors: Partial<Record<string, string>>;
  pending: boolean;
  onSubmit: (values: ContactFormValues) => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState(initial);
  const set = (field: keyof ContactFormValues) => (value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
  };
  return (
    <form
      className="flex flex-col gap-3 rounded-control border border-border p-3"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        onSubmit(values);
      }}
    >
      <FormField label="Name" error={errors["full_name"]}>
        {(field) => (
          <Input
            {...field}
            required
            value={values.full_name}
            onChange={(e) => {
              set("full_name")(e.target.value);
            }}
          />
        )}
      </FormField>
      <FormField label="Job title" error={errors["job_title"]}>
        {(field) => (
          <Input
            {...field}
            required
            value={values.job_title}
            onChange={(e) => {
              set("job_title")(e.target.value);
            }}
          />
        )}
      </FormField>
      <FormField
        label="Source page"
        hint="The public page that states the person and their title."
        error={errors["source_url"]}
      >
        {(field) => (
          <Input
            {...field}
            required
            type="url"
            value={values.source_url}
            onChange={(e) => {
              set("source_url")(e.target.value);
            }}
          />
        )}
      </FormField>
      <FormField
        label="Persona"
        hint="Leave empty to suggest it from the job title."
        error={errors["persona"]}
      >
        {(field) => (
          <Select
            {...field}
            value={values.persona}
            onChange={(e) => {
              set("persona")(e.target.value);
            }}
          >
            <option value="">Suggest from job title</option>
            {CONTACT_PERSONAS.map((persona) => (
              <option key={persona} value={persona}>
                {enumLabel(persona)}
              </option>
            ))}
          </Select>
        )}
      </FormField>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" type="submit" disabled={pending}>
          Save
        </Button>
      </div>
    </form>
  );
}
