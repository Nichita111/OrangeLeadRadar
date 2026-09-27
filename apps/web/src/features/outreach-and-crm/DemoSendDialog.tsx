import { useState } from "react";

import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";

/**
 * A made-up address for a demo send, derived when shown and never stored: a contact keeps no
 * email address (RULE-07). The `.example` domain can never receive mail.
 */
export function demoAddress(fullName: string, accountDomain: string | null | undefined): string {
  const local = fullName
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
    .join(".");
  const company = (accountDomain ?? "company.com").split(".").slice(0, -1).join(".") || "company";
  return `${local}@${company}.example`;
}

interface DemoSendDialogProps {
  to: { name: string; address: string } | null;
  subject: string;
  body: string;
  disabled: boolean;
  onSend: () => void;
}

/**
 * Previews the email as it would go out and "sends" it for a demo: nothing leaves LeadRadar
 * (RULE-06); confirming only marks the draft exported.
 */
export function DemoSendDialog({ to, subject, body, disabled, onSend }: DemoSendDialogProps) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      trigger={<Button disabled={disabled}>Send (demo)</Button>}
      title="Send email (demo)"
      description="A demo send: nothing leaves LeadRadar, and the draft is marked exported."
    >
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-text-secondary">To</dt>
        <dd className="m-0">
          {to === null ? (
            <span className="text-text-tertiary">
              No contact. Choose one under To and generate again.
            </span>
          ) : (
            <>
              {to.name} &lt;{to.address}&gt;
            </>
          )}
        </dd>
        <dt className="text-text-secondary">Subject</dt>
        <dd className="m-0 font-medium">{subject}</dd>
      </dl>
      <pre className="m-0 max-h-72 overflow-auto rounded-control border border-border bg-page p-3 font-sans text-body whitespace-pre-wrap">
        {body}
      </pre>
      <div className="flex justify-end gap-2">
        <Button
          onClick={() => {
            setOpen(false);
          }}
        >
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={to === null}
          onClick={() => {
            onSend();
            setOpen(false);
          }}
        >
          Send
        </Button>
      </div>
    </Dialog>
  );
}
