// The Blur-in text pattern of frontend Motion. Adapted from React Bits BlurText (TS-TW registry item;
// ADR-17): it plays once on arrival with the Motion design values, and shows its end state at once
// under reduced motion.
import { motion } from "motion/react";

import { EASING, ENTER_MS, STAGGER_MS } from "./values";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

interface BlurTextProps {
  text: string;
  as?: "h1" | "h2" | "p";
  className?: string;
}

const FROM = { filter: "blur(10px)", opacity: 0, y: -20 };
const TO = { filter: "blur(0px)", opacity: 1, y: 0 };

export function BlurText({ text, as: Tag = "h1", className }: BlurTextProps) {
  const reduced = usePrefersReducedMotion();
  const words = text.split(" ");
  return (
    <Tag className={className}>
      {words.map((word, index) => {
        const gap = index < words.length - 1 ? " " : "";
        if (reduced) {
          return (
            <span key={index} style={{ display: "inline-block", opacity: 1 }}>
              {word}
              {gap}
            </span>
          );
        }
        return (
          <motion.span
            key={index}
            style={{ display: "inline-block" }}
            initial={FROM}
            animate={TO}
            transition={{
              duration: ENTER_MS / 1000,
              delay: (index * STAGGER_MS) / 1000,
              ease: EASING,
            }}
          >
            {word}
            {gap}
          </motion.span>
        );
      })}
    </Tag>
  );
}
