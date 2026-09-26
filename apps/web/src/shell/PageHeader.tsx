import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  /** One sentence: what the screen is for and what a user does on it (FR-103). */
  lead: string;
  /** The one primary action, at the right (FR-104). */
  action?: ReactNode;
}

export function PageHeader({ title, lead, action }: PageHeaderProps) {
  return (
    <div className="flex items-end justify-between gap-6">
      <div className="flex max-w-3xl flex-col gap-1">
        <h1 className="m-0 text-title font-semibold">{title}</h1>
        <p className="m-0 text-text-secondary">{lead}</p>
      </div>
      {action}
    </div>
  );
}
