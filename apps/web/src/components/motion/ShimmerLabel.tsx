import { CircleNotchIcon } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactElement } from "react";

/** React Bits Shiny Text reduced to the approved running indicator and a static reduced-motion mark. */
export function ShimmerLabel({ children }: { children: string }): ReactElement {
  const reduced = useReducedMotion();
  if (reduced)
    return (
      <span className="inline-flex items-center gap-2">
        <CircleNotchIcon aria-hidden />
        {children}
      </span>
    );
  return (
    <span className="inline-flex items-center gap-2">
      <CircleNotchIcon aria-hidden className="animate-spin" />
      <motion.span
        animate={{ opacity: [0.55, 1, 0.55] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        {children}
      </motion.span>
    </span>
  );
}
