import { InfoIcon, SparkleIcon, WarningIcon, WarningCircleIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import { cn } from "./cn";

export type CalloutKind = "neutral" | "accent" | "caution" | "error";

const kinds: Record<CalloutKind, { icon: ReactNode; tone: string }> = {
  neutral: { icon: <InfoIcon size={20} aria-hidden />, tone: "bg-cool-soft text-cool" },
  accent: { icon: <SparkleIcon size={20} aria-hidden />, tone: "bg-accent-soft text-accent-ink" },
  caution: { icon: <WarningIcon size={20} aria-hidden />, tone: "bg-caution-soft text-caution" },
  error: {
    icon: <WarningCircleIcon size={20} aria-hidden />,
    tone: "bg-negative-soft text-negative",
  },
};

interface CalloutProps {
  kind: CalloutKind;
  /** The first sentence, in bold, when it names the state (FR-121). */
  lead?: string;
  children?: ReactNode;
}

/** A state that stays true while the screen is open (FR-120, FR-121). */
export function Callout({ kind, lead, children }: CalloutProps) {
  const { icon, tone } = kinds[kind];
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cn("flex items-start gap-3 rounded-control px-3.5 py-3", tone)}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <p className="m-0">
        {lead !== undefined && <strong className="font-semibold">{lead} </strong>}
        {children}
      </p>
    </div>
  );
}
