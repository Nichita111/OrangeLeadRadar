import * as ToastPrimitive from "@radix-ui/react-toast";
import { XIcon } from "@phosphor-icons/react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { TOAST_VISIBLE_MS } from "./motion/values";

interface ToastItem {
  id: number;
  message: string;
}

interface ToastApi {
  /** Confirms a completed action. An error is never a toast (FR-120). */
  notify: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (api === null) {
    throw new Error("useToast needs a ToastProvider.");
  }
  return api;
}

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const notify = useCallback((message: string) => {
    nextId += 1;
    const id = nextId;
    setItems((current) => [...current, { id, message }]);
  }, []);
  const api = useMemo(() => ({ notify }), [notify]);
  return (
    <ToastContext.Provider value={api}>
      <ToastPrimitive.Provider duration={TOAST_VISIBLE_MS} label="Notification">
        {children}
        {items.map((item) => (
          <ToastPrimitive.Root
            key={item.id}
            onOpenChange={(open) => {
              if (!open) {
                setItems((current) => current.filter((other) => other.id !== item.id));
              }
            }}
            className="flex items-center gap-3 rounded-card border border-border bg-surface px-4 py-3 shadow-overlay"
          >
            <ToastPrimitive.Title className="font-medium">{item.message}</ToastPrimitive.Title>
            <ToastPrimitive.Close
              aria-label="Dismiss"
              className="ml-auto inline-flex size-control-small items-center justify-center rounded-control hover:bg-page"
            >
              <XIcon size={16} aria-hidden />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed right-4 bottom-4 z-50 flex w-96 max-w-full flex-col gap-2" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
