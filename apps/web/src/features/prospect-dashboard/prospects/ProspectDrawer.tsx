/**
 * `FR-130`: the drawer over the right side of the list, without moving the rows: name and band,
 * Priority with Fit and Intent in words, the row's top signals, and Open full explanation.
 * Escape or the close button dismisses it and returns focus to the row's button.
 */
import { XIcon } from "@phosphor-icons/react";
import * as RadixDialog from "@radix-ui/react-dialog";
import type { RefObject } from "react";
import { Link } from "react-router-dom";

import type { ProspectRow } from "../../../api/prospects";
import { BandChip } from "../../../components/score/BandChip";
import { ScoreFigures } from "../../../components/score/ScoreFigures";
import {
  formatAbsoluteDateTime,
  formatRelativeDate,
  strengthLabel,
} from "../../../shell/formatting";

export function ProspectDrawer({
  row,
  onClose,
  returnFocusRef,
}: {
  row: ProspectRow;
  onClose: () => void;
  returnFocusRef: RefObject<HTMLElement | null>;
}) {
  return (
    <RadixDialog.Root
      open
      modal={false}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <RadixDialog.Portal>
        <RadixDialog.Content
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnFocusRef.current?.focus();
          }}
          className="fixed bottom-0 right-0 top-14 z-40 flex w-[380px] flex-col gap-4 overflow-y-auto border-l border-border bg-surface p-6"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <RadixDialog.Title className="text-[15px] font-semibold text-text">
                {row.account.name}
              </RadixDialog.Title>
              <BandChip standing={row.standing} band={row.band} />
            </div>
            <RadixDialog.Close aria-label="Close" className="text-text-tertiary">
              <XIcon size={20} aria-hidden="true" />
            </RadixDialog.Close>
          </div>
          <ScoreFigures priority={row.priority} fit={row.fit} intent={row.intent} />
          {row.top_signals.length > 0 && (
            <section aria-label="Strongest signals" className="flex flex-col gap-1">
              <h3 className="text-[12.5px] font-medium uppercase tracking-wide text-text-tertiary">
                Strongest signals
              </h3>
              <ul className="flex flex-col gap-1 text-sm text-text">
                {row.top_signals.map((signal) => (
                  <li key={signal.question_key}>
                    {signal.question_text}, {strengthLabel(signal.strength)},{" "}
                    <span title={formatAbsoluteDateTime(signal.observed_at)}>
                      {formatRelativeDate(signal.observed_at)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <Link
            to={`/accounts/${row.account.id}`}
            className="inline-flex items-center justify-center rounded-control border border-border px-4 text-sm font-medium text-text hover:bg-page"
            style={{ height: "var(--ctl-button)" }}
          >
            Open full explanation
          </Link>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
