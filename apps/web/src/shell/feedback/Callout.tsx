import { CheckCircleIcon, InfoIcon, WarningIcon, XCircleIcon } from "@phosphor-icons/react";
import type { ReactElement, ReactNode } from "react";

const KINDS = {
  neutral: { Icon: InfoIcon, classes: "border-border bg-surface" },
  accent: { Icon: CheckCircleIcon, classes: "border-accent bg-accent-soft" },
  caution: { Icon: WarningIcon, classes: "border-caution bg-caution-soft" },
  error: { Icon: XCircleIcon, classes: "border-negative bg-negative-soft" },
} as const;

export function Callout({
  kind,
  title,
  children,
}: {
  kind: keyof typeof KINDS;
  title?: string;
  children: ReactNode;
}): ReactElement {
  const { Icon, classes } = KINDS[kind];
  return (
    <div className={`flex gap-3 rounded-card border p-4 ${classes}`}>
      <Icon aria-hidden="true" size={20} />
      <div>
        {title !== undefined ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}
