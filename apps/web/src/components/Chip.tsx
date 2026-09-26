import type { ReactNode } from "react";

import { cn } from "./cn";

export type ChipTone = "neutral" | "accent" | "positive" | "negative" | "caution" | "cool";

const tones: Record<ChipTone, string> = {
  neutral: "bg-page text-text-secondary border border-border",
  accent: "bg-accent-soft text-accent-ink",
  positive: "bg-positive-soft text-positive",
  negative: "bg-negative-soft text-negative",
  caution: "bg-caution-soft text-caution",
  cool: "bg-cool-soft text-cool",
};

interface ChipProps {
  tone?: ChipTone;
  children: ReactNode;
}

/** State is always carried by the text as well as the tone (FR-107). */
export function Chip({ tone = "neutral", children }: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-hint font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
