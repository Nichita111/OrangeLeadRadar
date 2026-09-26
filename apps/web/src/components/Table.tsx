/**
 * The shared table shell: borders (not shadows) between rows, per [Visual language]
 * (/architecture/services/frontend.md#visual-language).
 */
import type { ReactNode, ThHTMLAttributes } from "react";

export function Table({ children, caption }: { children: ReactNode; caption: string }) {
  return (
    <table className="w-full border-collapse overflow-hidden rounded-card border border-border bg-surface text-sm">
      <caption className="sr-only">{caption}</caption>
      {children}
    </table>
  );
}

export function TableHead({ children }: { children: ReactNode }) {
  return <thead className="border-b border-border text-left">{children}</thead>;
}

export function TableHeaderCell({ children, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className="px-4 py-3 text-[12.5px] font-medium uppercase tracking-wide text-text-tertiary"
      {...props}
    >
      {children}
    </th>
  );
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TableRow({ children }: { children: ReactNode }) {
  return <tr className="border-b border-border last:border-0">{children}</tr>;
}

export function TableCell({ children, colSpan }: { children: ReactNode; colSpan?: number }) {
  return (
    <td className="px-4 py-3 text-text" colSpan={colSpan}>
      {children}
    </td>
  );
}
