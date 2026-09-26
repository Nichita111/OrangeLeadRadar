/**
 * The dialog shell of [Confirmation](/architecture/services/frontend.md#confirmation) (`FR-123`):
 * titled with the action, Escape closes it and returns focus to the control that opened it (both
 * native to Radix Dialog). `Dialog` holds a form or other content; [`ConfirmDialog`](#confirmdialog)
 * is the one-sentence confirmation shape of `FR-015`.
 */
import { XIcon } from "@phosphor-icons/react";
import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

import { Button } from "./Button";

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}

export function Dialog({ open, onOpenChange, title, children }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <RadixDialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-surface p-6 shadow-lg">
          <div className="mb-4 flex items-center justify-between">
            <RadixDialog.Title className="text-[15px] font-semibold text-text">
              {title}
            </RadixDialog.Title>
            <RadixDialog.Close aria-label="Close" className="text-text-tertiary">
              <XIcon size={20} />
            </RadixDialog.Close>
          </div>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The action, e.g. "Disable user" (`FR-123`). */
  title: string;
  /** What changes and what is kept, in one sentence. */
  description: ReactNode;
  /** Named after its verb, e.g. "Disable user", never "OK" (`FR-123`). */
  confirmLabel: string;
  onConfirm: () => void;
  confirmPending?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  confirmPending = false,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={title}>
      <p className="mb-6 text-sm text-text-secondary">{description}</p>
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          Cancel
        </Button>
        <Button type="button" variant="primary" onClick={onConfirm} disabled={confirmPending}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
