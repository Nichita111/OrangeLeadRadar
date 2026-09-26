import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ReactElement, ReactNode } from "react";

interface DialogProps {
  trigger: ReactElement;
  title: string;
  /** One sentence: what changes and what is kept (FR-123). */
  description: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}

/** A modal dialog; its trigger gets focus back when it closes (FR-123). */
export function Dialog({ trigger, title, description, open, onOpenChange, children }: DialogProps) {
  const controlled = {
    ...(open === undefined ? {} : { open }),
    ...(onOpenChange === undefined ? {} : { onOpenChange }),
  };
  return (
    <DialogPrimitive.Root {...controlled}>
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-text/40" />
        <DialogPrimitive.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[520px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-auto rounded-card border border-border bg-surface p-6 shadow-overlay">
          <DialogPrimitive.Title className="m-0 text-section font-semibold">
            {title}
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="m-0 text-text-secondary">
            {description}
          </DialogPrimitive.Description>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
