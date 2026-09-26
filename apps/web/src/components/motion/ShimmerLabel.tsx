/**
 * [React Bits](https://reactbits.dev) "Shimmer" (Text animations), copied into owned code
 * ([ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)): the one running
 * indicator [Motion](/architecture/services/frontend.md#motion) allows to loop (`FR-124`,
 * `FR-126`) — the Refreshing label on [Accounts]
 * (/features/accounts-and-discovery.md#accounts) and the running status of a run on
 * [Runs](/features/signal-pipeline.md#runs). Only `background-position` (a transform-equivalent
 * paint property, no layout) animates. Collapses to the plain label under
 * `prefers-reduced-motion` (`FR-125`), which then shows a static mark with its label.
 */
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Loops; not one of the [Motion](/architecture/services/frontend.md#motion) design values, which
 * only names one-shot durations. */
const SHIMMER_CYCLE_S = 1.6;

export function ShimmerLabel({ children }: { children: ReactNode }) {
  const prefersReducedMotion = useReducedMotion();

  if (prefersReducedMotion === true) {
    return <span>{children}</span>;
  }

  return (
    <motion.span
      className="bg-clip-text text-transparent"
      style={{
        backgroundImage:
          "linear-gradient(90deg, var(--color-text-tertiary) 0%, var(--color-text) 50%, var(--color-text-tertiary) 100%)",
        backgroundSize: "200% 100%",
      }}
      animate={{ backgroundPositionX: ["0%", "-200%"] }}
      transition={{ duration: SHIMMER_CYCLE_S, repeat: Infinity, ease: "linear" }}
    >
      {children}
    </motion.span>
  );
}
