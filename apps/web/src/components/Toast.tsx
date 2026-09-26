/**
 * `FR-120`: a toast for a completed action, announced as a status, dismissible, leaving by
 * itself after the confirmation time of [Motion](/architecture/services/frontend.md#motion)
 * (`TOAST_VISIBLE_MS`, a design value, not a runtime configuration key). An error is never a
 * toast ([FR-120](/architecture/services/frontend.md#messages-and-feedback)); use
 * [`Callout`](./Callout.tsx) instead.
 */
import { XIcon } from "@phosphor-icons/react";
import * as RadixToast from "@radix-ui/react-toast";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

/** The Motion section's "Toast visible" design value. */
const TOAST_VISIBLE_MS = 6000;

interface ToastMessage {
  id: string;
  message: string;
}

interface ToastContextValue {
  showToast: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (context === null) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback((message: string) => {
    const id = crypto.randomUUID();
    setToasts((current) => [...current, { id, message }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      <RadixToast.Provider duration={TOAST_VISIBLE_MS}>
        {children}
        {toasts.map((toast) => (
          <RadixToast.Root
            key={toast.id}
            duration={TOAST_VISIBLE_MS}
            onOpenChange={(open) => {
              if (!open) {
                dismiss(toast.id);
              }
            }}
            className="flex items-center justify-between gap-3 rounded-card border border-border bg-surface px-4 py-3 text-sm text-text shadow-lg data-[state=open]:animate-none"
          >
            <RadixToast.Description>{toast.message}</RadixToast.Description>
            <RadixToast.Close aria-label="Dismiss" className="shrink-0 text-text-tertiary">
              <XIcon size={16} />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-4 right-4 z-50 flex w-96 flex-col gap-2 outline-none" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}
