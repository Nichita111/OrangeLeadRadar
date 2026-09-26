import type { ReactElement } from "react";

/** `FR-006`: a `403` shows a "Not allowed" page naming the role required. */
export function NotAllowed({ requiredRole }: { requiredRole: string }): ReactElement {
  return (
    <div className="p-6">
      <h1 className="text-page-title text-text">Not allowed</h1>
      <p className="mt-2 text-text-secondary">This screen needs the {requiredRole} role.</p>
    </div>
  );
}
