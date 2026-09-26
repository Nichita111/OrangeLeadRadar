import { XIcon } from "@phosphor-icons/react";
import * as RadixDialog from "@radix-ui/react-dialog";
import type { RefObject } from "react";

import type { ProspectRow } from "../../../api/prospectsAndEvidence";
import { ButtonLink } from "../../../components/Button";
import { BandChip } from "../BandChip";
import { ScoreFigures } from "../ScoreFigures";
import { TopSignals } from "../TopSignals";

/**
 * FR-130: the drawer over the right side of the list, without moving the rows: name and band,
 * Priority with Fit and Intent in words, the row's top signals, and Open full explanation.
 * Escape or the close button dismisses it and returns focus to the row's button.
 */
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
          className="fixed top-14 right-0 bottom-0 z-40 flex w-96 flex-col gap-4 overflow-y-auto border-l border-border bg-surface p-6"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <RadixDialog.Title className="m-0 text-section font-semibold">
                {row.account.name}
              </RadixDialog.Title>
              <BandChip standing={row.standing} band={row.band} />
            </div>
            <RadixDialog.Close aria-label="Close" className="text-text-tertiary">
              <XIcon size={20} aria-hidden />
            </RadixDialog.Close>
          </div>
          <ScoreFigures priority={row.priority} fit={row.fit} intent={row.intent} />
          {row.top_signals.length > 0 && (
            <section aria-label="Strongest signals" className="flex flex-col gap-1">
              <h3 className="m-0 text-hint font-medium text-text-tertiary uppercase">
                Strongest signals
              </h3>
              <TopSignals signals={row.top_signals} />
            </section>
          )}
          <ButtonLink to={`/accounts/${row.account.id}`}>Open full explanation</ButtonLink>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
