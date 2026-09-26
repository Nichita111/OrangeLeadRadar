import { useEffect, type ReactElement } from "react";

/**
 * Every route of [Routes](/architecture/services/frontend.md#routes) renders this until its own
 * task builds the screen: the screen's label as the page title, and a short placeholder body.
 */
export function ScreenPlaceholder({ label }: { label: string }): ReactElement {
  useEffect(() => {
    document.title = `${label} — LeadRadar`;
  }, [label]);

  return (
    <div className="p-6">
      <h1 className="text-page-title font-[var(--text-page-title--font-weight)] text-text">
        {label}
      </h1>
      <p className="mt-2 text-text-secondary">This screen is not built yet.</p>
    </div>
  );
}
