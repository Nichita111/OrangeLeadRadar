/**
 * [React Bits](https://reactbits.dev) "Blur-in text" (Text animations), copied into owned code
 * ([ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)): once on arrival,
 * the headline of an empty state and of Sign in settles in. The Motion intro allows only
 * transform and opacity to animate (`FR-127`), so the reveal is a fade with a small scale
 * settle, never a CSS blur filter, despite the pattern's name. Collapses to the end state under
 * `prefers-reduced-motion` (`FR-125`).
 */
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** The Motion section's "Enter" design value. */
const ENTER_S = 0.2;
const EASE = [0.16, 1, 0.3, 1] as const;

export interface BlurInTextProps {
  as?: "h1" | "p";
  className?: string;
  children: ReactNode;
}

export function BlurInText({ as = "p", className, children }: BlurInTextProps) {
  const prefersReducedMotion = useReducedMotion();

  if (prefersReducedMotion === true) {
    return as === "h1" ? (
      <h1 className={className}>{children}</h1>
    ) : (
      <p className={className}>{children}</p>
    );
  }

  const transition = { duration: ENTER_S, ease: EASE };
  const initial = { opacity: 0, scale: 0.97 };
  const animate = { opacity: 1, scale: 1 };

  return as === "h1" ? (
    <motion.h1 className={className} initial={initial} animate={animate} transition={transition}>
      {children}
    </motion.h1>
  ) : (
    <motion.p className={className} initial={initial} animate={animate} transition={transition}>
      {children}
    </motion.p>
  );
}
