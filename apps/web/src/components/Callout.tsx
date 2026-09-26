/**
 * `FR-121`: a callout for a state that stays true while the screen is open, carrying an icon and
 * one to two sentences, its kind neutral, accent, caution or error, each with its own icon.
 */
import {
  CheckCircleIcon,
  InfoIcon,
  WarningIcon,
  WarningCircleIcon,
  type Icon,
} from "@phosphor-icons/react";
import type { ReactNode } from "react";

export type CalloutKind = "neutral" | "accent" | "caution" | "error";

const KIND_ICON: Record<CalloutKind, Icon> = {
  neutral: InfoIcon,
  accent: CheckCircleIcon,
  caution: WarningIcon,
  error: WarningCircleIcon,
};

const KIND_CLASSES: Record<CalloutKind, string> = {
  neutral: "bg-page text-text border-border",
  accent: "bg-accent-soft text-accent-ink border-accent-soft",
  caution: "bg-caution-soft text-caution border-caution-soft",
  error: "bg-negative-soft text-negative border-negative-soft",
};

export function Callout({
  kind = "neutral",
  children,
}: {
  kind?: CalloutKind;
  children: ReactNode;
}) {
  const CalloutIcon = KIND_ICON[kind];
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`flex items-start gap-2 rounded-control border px-3 py-2.5 text-sm ${KIND_CLASSES[kind]}`}
    >
      <CalloutIcon size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
