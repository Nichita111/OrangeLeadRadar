import * as AlertDialog from "@radix-ui/react-alert-dialog";
import type { ReactElement } from "react";

import { Button } from "./Button";

interface ConfirmDialogProps {
  trigger: ReactElement;
  /** The action, as FR-123 asks. */
  title: string;
  /** One sentence: what changes and what is kept. */
  description: string;
  /** The verb button, never OK. */
  confirmLabel: string;
  onConfirm: () => void;
}

/** FR-015, FR-123: cancel first, the confirming button last; Escape closes and focus returns. */
export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger asChild>{trigger}</AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-text/40" />
        <AlertDialog.Content className="fixed top-1/2 left-1/2 z-50 flex w-[460px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-card border border-border bg-surface p-6 shadow-overlay">
          <AlertDialog.Title className="m-0 text-section font-semibold">{title}</AlertDialog.Title>
          <AlertDialog.Description className="m-0 text-text-secondary">
            {description}
          </AlertDialog.Description>
          <div className="flex justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <Button variant="secondary">Cancel</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <Button variant="primary" onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
