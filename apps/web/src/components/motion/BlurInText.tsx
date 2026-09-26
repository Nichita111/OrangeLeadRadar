import { motion, useReducedMotion } from "motion/react";
import type { ReactElement } from "react";

import { MOTION } from "../../styles/motion";

/** React Bits Blur Text reduced to the one approved Blur-in pattern. */
export function BlurInText({ children }: { children: string }): ReactElement {
  const reduced = useReducedMotion();
  return (
    <motion.span
      initial={reduced ? false : { opacity: 0, filter: "blur(8px)" }}
      animate={{ opacity: 1, filter: "blur(0px)" }}
      transition={{ duration: reduced ? 0 : MOTION.enterMs / 1000 }}
    >
      {children}
    </motion.span>
  );
}
