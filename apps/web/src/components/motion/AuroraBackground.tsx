/**
 * [React Bits](https://reactbits.dev) "Aurora background" (Backgrounds), copied into owned code
 * ([ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)): the brand
 * panel's ambience on Sign in only. It never loops (`FR-126`) — it settles once, on arrival, to
 * the still gradient of [`AuroraFallback`](./AuroraFallback.tsx), animating only opacity and
 * transform (`FR-127`). This is the module `SignInScreen` imports through `React.lazy` for
 * `FR-128`'s lazy load; default-exported so `React.lazy` can resolve it.
 */
import { motion, useReducedMotion } from "motion/react";

import { AURORA_GRADIENT } from "./AuroraFallback";

const ENTER_S = 0.6;
const EASE = [0.16, 1, 0.3, 1] as const;

function AuroraBackground() {
  const prefersReducedMotion = useReducedMotion();

  if (prefersReducedMotion === true) {
    return (
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{ background: AURORA_GRADIENT }}
      />
    );
  }

  return (
    <motion.div
      aria-hidden="true"
      className="absolute inset-0"
      style={{ background: AURORA_GRADIENT }}
      initial={{ opacity: 0, scale: 1.04 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: ENTER_S, ease: EASE }}
    />
  );
}

export default AuroraBackground;
