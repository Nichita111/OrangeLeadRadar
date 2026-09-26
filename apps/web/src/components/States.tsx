/**
 * The four states every data view renders (`FR-005`, `FR-118`): loading (skeleton rows sized like
 * the content, so layout does not move when it arrives), empty (what would appear and the
 * action that creates it), error (the message and Retry) and unavailable (`503`/`429`: which
 * dependency and what still works, per [Degradation]
 * (/architecture/overview.md#degradation)).
 */
import { CheckIcon } from "@phosphor-icons/react";

import { Button } from "./Button";
import { TableCell, TableRow } from "./Table";

export function SkeletonRows({ rows, columns }: { rows: number; columns: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, rowIndex) => (
        <TableRow key={rowIndex}>
          {Array.from({ length: columns }, (_, columnIndex) => (
            <TableCell key={columnIndex}>
              <div className="h-4 w-full max-w-40 rounded bg-page" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

export function EmptyState({
  message,
  actionLabel,
  onAction,
}: {
  message: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <p className="max-w-sm text-sm text-text-secondary">{message}</p>
      <Button variant="primary" onClick={onAction}>
        {actionLabel}
      </Button>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <p className="max-w-sm text-sm text-negative">{message}</p>
      <Button variant="secondary" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function UnavailableState({
  dependency,
  stillWorks,
}: {
  dependency: string;
  stillWorks: string[];
}) {
  return (
    <div className="flex flex-col gap-3 px-6 py-16">
      <p className="text-sm text-text">
        <strong>{dependency}</strong> is unavailable right now.
      </p>
      {stillWorks.length > 0 ? (
        <ul className="flex flex-col gap-1.5 text-sm text-text-secondary">
          {stillWorks.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <CheckIcon size={16} className="text-positive" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-text-secondary">Nothing else works while it is down.</p>
      )}
    </div>
  );
}
