import type { ReactElement, ReactNode } from "react";
export function Toolbar({ children }: { children: ReactNode }): ReactElement {
  return (
    <div role="toolbar" className="flex items-center gap-3 border-y border-border py-3">
      {children}
    </div>
  );
}
