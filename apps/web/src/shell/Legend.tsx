import type { ReactElement, ReactNode } from "react";
export function Legend({ children }: { children: ReactNode }): ReactElement {
  return (
    <aside aria-label="Legend" className="mt-3 text-sm text-text-secondary">
      {children}
    </aside>
  );
}
