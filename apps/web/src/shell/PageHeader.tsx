import type { ReactElement, ReactNode } from "react";

export function PageHeader({
  title,
  lead,
  action,
}: {
  title: string;
  lead: string;
  action?: ReactNode;
}): ReactElement {
  return (
    <header className="flex items-start justify-between gap-6">
      <div>
        <h1 className="text-page-title font-semibold text-text">{title}</h1>
        <p className="mt-1 text-text-secondary">{lead}</p>
      </div>
      {action}
    </header>
  );
}
