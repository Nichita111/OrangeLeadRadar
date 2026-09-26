import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState, type ReactElement, type ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../components/ui/alert-dialog";
import { Button } from "../components/ui/button";
import { MOTION } from "../styles/motion";

/**
 * `FR-015`, `FR-123`: titled with the action, one sentence saying what changes and what is kept,
 * Cancel first, the confirming button last and named after its verb. Radix's `AlertDialog`
 * already closes on Escape and returns focus to the opener.
 */
export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel,
  onConfirm,
  open,
  onOpenChange,
}: {
  trigger?: ReactNode;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}): ReactElement {
  const reduced = useReducedMotion();
  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = open ?? internalOpen;
  const changeOpen = (nextOpen: boolean): void => {
    if (open === undefined) setInternalOpen(nextOpen);
    onOpenChange?.(nextOpen);
  };
  const initial = reduced ? false : { opacity: 0 };
  const animate = {
    opacity: 1,
    transition: { duration: reduced ? 0 : MOTION.enterMs / 1000, ease: MOTION.easing },
  };
  const exit = {
    opacity: reduced ? 1 : 0,
    transition: { duration: reduced ? 0 : MOTION.exitMs / 1000, ease: MOTION.easing },
  };
  return (
    <AlertDialog open={isOpen} onOpenChange={changeOpen}>
      {trigger !== undefined ? <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger> : null}
      <AlertDialogPortal forceMount>
        <AnimatePresence>
          {isOpen ? (
            <>
              <AlertDialogOverlay asChild forceMount>
                <motion.div
                  data-overlay
                  className="fixed inset-0 bg-text/40"
                  initial={initial}
                  animate={animate}
                  exit={exit}
                />
              </AlertDialogOverlay>
              <AlertDialogContent asChild forceMount>
                <motion.div
                  className="fixed top-1/2 left-1/2 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-surface p-6 shadow-md"
                  initial={initial}
                  animate={animate}
                  exit={exit}
                >
                  <AlertDialogTitle className="text-text text-base font-semibold">
                    {title}
                  </AlertDialogTitle>
                  <AlertDialogDescription className="mt-2 text-sm text-text-secondary">
                    {description}
                  </AlertDialogDescription>
                  <div className="mt-6 flex justify-end gap-3">
                    <AlertDialogCancel asChild>
                      <Button variant="secondary">Cancel</Button>
                    </AlertDialogCancel>
                    <AlertDialogAction asChild>
                      <Button variant="primary" onClick={onConfirm}>
                        {confirmLabel}
                      </Button>
                    </AlertDialogAction>
                  </div>
                </motion.div>
              </AlertDialogContent>
            </>
          ) : null}
        </AnimatePresence>
      </AlertDialogPortal>
    </AlertDialog>
  );
}
