import { useState } from "react";
import { Link, useParams } from "react-router";

import type { Schemas } from "../../api/contract";
import {
  useContacts,
  useOutreachDrafts,
  useOutreachMutations,
  type OutreachDraft,
  type OutreachDraftChannel,
} from "../../api/contactsAndOutreach";
import { useFindings, type FindingView } from "../../api/prospectsAndEvidence";
import { useAccount } from "../../api/referenceData";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { FormField } from "../../components/FormField";
import { Input, Select } from "../../components/controls";
import { Skeleton } from "../../components/Skeleton";
import { enumLabel } from "../../shell/format";
import { RelativeTime } from "../../shell/RelativeTime";
import { DataView } from "../../shell/states/DataView";
import { WithService } from "../../shell/WithService";
import { ContactsSection } from "./ContactsSection";

const CHANNELS: { value: OutreachDraftChannel; label: string }[] = [
  { value: "EMAIL", label: "Email" },
  { value: "LINKEDIN_INMAIL", label: "LinkedIn InMail" },
];

/**
 * Outreach composer, `/accounts/:id/outreach`, with the service from the selector. WF-19. Generates
 * a grounded draft (`API-56`), edits and exports it (`API-58`); nothing is sent from LeadRadar.
 */
export function OutreachComposerScreen() {
  const { id = "" } = useParams();
  return <WithService>{(service) => <Composer accountId={id} service={service} />}</WithService>;
}

function Composer({ accountId, service }: { accountId: string; service: Schemas["Service"] }) {
  const account = useAccount(accountId);
  const contacts = useContacts(accountId);
  const drafts = useOutreachDrafts(accountId, service.id);
  const findings = useFindings(accountId, service.id, "ACTIVE");
  const { generate, update } = useOutreachMutations(accountId, service.id);

  const [channel, setChannel] = useState<OutreachDraftChannel>("EMAIL");
  const [contactId, setContactId] = useState("");
  const [draft, setDraft] = useState<OutreachDraft | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  function open(next: OutreachDraft) {
    setDraft(next);
    setSubject(next.subject ?? "");
    setBody(next.body);
    setNotice(null);
  }

  function edits(current: OutreachDraft) {
    return {
      ...(current.channel === "EMAIL" && subject !== (current.subject ?? "") ? { subject } : {}),
      ...(body !== current.body ? { body } : {}),
    };
  }

  function save(current: OutreachDraft) {
    update.mutate(
      { id: current.id, body: edits(current) },
      {
        onSuccess: (saved) => {
          setDraft(saved);
          setNotice("Saved.");
        },
      },
    );
  }

  function exportDraft(current: OutreachDraft, how: "copy" | "download") {
    const text = current.channel === "EMAIL" ? `Subject: ${subject}\n\n${body}` : body;
    if (how === "copy") {
      void navigator.clipboard.writeText(text);
    } else {
      const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `outreach-${current.id}.txt`;
      link.click();
      URL.revokeObjectURL(url);
    }
    update.mutate(
      { id: current.id, body: { ...edits(current), status: "EXPORTED" } },
      {
        onSuccess: (saved) => {
          setDraft(saved);
          setNotice(how === "copy" ? "Copied to the clipboard." : "Downloaded.");
        },
      },
    );
  }

  const error = generate.error ?? update.error;
  // FR-086, FR-090: the counted positive signals, most points first; none disables Generate.
  const signals = countedPositive(findings.data ?? []);
  const noSignal = findings.isSuccess && signals.length === 0;
  const cited = new Set((draft?.findings ?? []).map((finding) => finding.id));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="m-0 text-title font-semibold">
          {account.data?.name ?? "Account"} · {service.name}
        </h1>
        <Link to={`/accounts/${accountId}`} className="text-accent-ink underline">
          Back to account detail
        </Link>
      </header>

      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <aside className="flex flex-col gap-6">
          <section className="flex flex-col gap-3">
            <h2 className="m-0 text-section font-semibold">Signals the draft can use</h2>
            <DataView
              query={findings}
              isEmpty={(items) => countedPositive(items).length === 0}
              skeleton={<Skeleton className="h-16 w-full" />}
              empty={{ message: "No positive signal counts for this service yet.", action: null }}
            >
              {(items) => (
                <ol className="m-0 flex flex-col gap-2 pl-5">
                  {countedPositive(items).map((finding) => (
                    <li key={finding.id}>
                      <span className="font-medium">{finding.question.text}</span>
                      {cited.has(finding.id) && (
                        <span className="ml-2 text-hint text-accent-ink">Cited</span>
                      )}
                      <blockquote className="m-0 mt-0.5 text-text-secondary">
                        “{finding.quote}”
                      </blockquote>
                    </li>
                  ))}
                </ol>
              )}
            </DataView>
          </section>
          <ContactsSection accountId={accountId} />
          <section className="flex flex-col gap-3">
            <h2 className="m-0 text-section font-semibold">Earlier drafts</h2>
            <DataView
              query={drafts}
              isEmpty={(items) => items.length === 0}
              skeleton={<Skeleton className="h-16 w-full" />}
              empty={{ message: "No drafts yet.", action: null }}
            >
              {(items) => (
                <ul className="m-0 flex list-none flex-col gap-1 p-0">
                  {items.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => {
                          open(item);
                        }}
                        aria-current={draft?.id === item.id ? "true" : undefined}
                        className="w-full rounded-control px-2 py-1.5 text-left hover:bg-page aria-[current=true]:bg-accent-soft"
                      >
                        {enumLabel(item.channel)} · <RelativeTime at={item.created_at} /> ·{" "}
                        {enumLabel(item.status)}
                        {item.contact !== null && ` · ${item.contact.full_name}`}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </DataView>
          </section>
        </aside>

        <section className="flex flex-col gap-4">
          <fieldset className="m-0 flex gap-4 border-0 p-0">
            <legend className="mb-1.5 font-medium">Channel</legend>
            {CHANNELS.map((option) => (
              <label key={option.value} className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name="channel"
                  value={option.value}
                  checked={channel === option.value}
                  onChange={() => {
                    setChannel(option.value);
                  }}
                />
                {option.label}
              </label>
            ))}
          </fieldset>
          <FormField label="To" hint="Optional.">
            {(field) => (
              <Select
                {...field}
                value={contactId}
                onChange={(e) => {
                  setContactId(e.target.value);
                }}
              >
                <option value="">No contact</option>
                {(contacts.data ?? []).map((contact) => (
                  <option key={contact.id} value={contact.id}>
                    {contact.full_name} — {contact.job_title}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
          <div className="flex flex-col items-start gap-2">
            <Button
              variant="primary"
              disabled={generate.isPending || noSignal}
              onClick={() => {
                generate.mutate(
                  { channel, ...(contactId === "" ? {} : { contact_id: contactId }) },
                  { onSuccess: open },
                );
              }}
            >
              {generate.isPending ? "Generating…" : "Generate"}
            </Button>
            {noSignal && (
              <p className="m-0 text-hint text-text-tertiary">
                Generate needs at least one in-force positive signal for {service.name}.
              </p>
            )}
          </div>

          {error !== null && <Callout kind="error">{error.message}</Callout>}

          {draft !== null && (
            <div className="flex flex-col gap-4">
              {draft.channel === "EMAIL" && (
                <FormField label="Subject">
                  {(field) => (
                    <Input
                      {...field}
                      value={subject}
                      onChange={(e) => {
                        setSubject(e.target.value);
                      }}
                    />
                  )}
                </FormField>
              )}
              <FormField label="Body">
                {(field) => (
                  <textarea
                    {...field}
                    rows={12}
                    value={body}
                    onChange={(e) => {
                      setBody(e.target.value);
                    }}
                    className="w-full rounded-control border border-control-border bg-surface p-3 text-text"
                  />
                )}
              </FormField>
              <div className="flex flex-col gap-2">
                <h3 className="m-0 font-medium">Uses signals</h3>
                <ol className="m-0 flex flex-col gap-2 pl-5">
                  {draft.findings.map((finding) => (
                    <li key={finding.id}>
                      <span className="font-medium">{finding.question_text}</span>
                      <blockquote className="m-0 mt-0.5 text-text-secondary">
                        “{finding.quote}”
                      </blockquote>
                    </li>
                  ))}
                </ol>
              </div>
              <p className="m-0 text-hint text-text-tertiary">
                Nothing is sent from LeadRadar. {enumLabel(draft.status)}
                {draft.edited ? " · edited" : ""} · by {draft.created_by_name}
              </p>
              {notice !== null && <Callout kind="neutral">{notice}</Callout>}
              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  onClick={() => {
                    exportDraft(draft, "copy");
                  }}
                  disabled={update.isPending}
                >
                  Copy
                </Button>
                <Button
                  onClick={() => {
                    exportDraft(draft, "download");
                  }}
                  disabled={update.isPending}
                >
                  Download .txt
                </Button>
                <Button
                  variant="primary"
                  onClick={() => {
                    save(draft);
                  }}
                  disabled={update.isPending}
                >
                  Save
                </Button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/** The findings that count positively in the current score, most points first (`FR-086`). */
function countedPositive(items: readonly FindingView[]): FindingView[] {
  return items
    .filter(
      (finding) =>
        finding.question.polarity === "POSITIVE" && finding.points !== null && finding.points > 0,
    )
    .sort((left, right) => (right.points ?? 0) - (left.points ?? 0));
}
