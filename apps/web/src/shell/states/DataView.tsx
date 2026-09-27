import { CheckCircleIcon } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { NotAllowed } from "./NotAllowed";
import { screenWording, type ScreenWording } from "./degradation";

// The parts of a TanStack Query result a data view reads; a `UseQueryResult` fits.
export type DataViewQuery<T> =
  | { status: "pending"; refetch: () => unknown }
  | { status: "error"; error: Error; refetch: () => unknown }
  | { status: "success"; data: T; refetch: () => unknown };

interface DataViewProps<T> {
  query: DataViewQuery<T>;
  isEmpty: (data: T) => boolean;
  /** Skeleton shapes the size of what they stand in for (FR-118). */
  skeleton: ReactNode;
  /** A sentence saying what would appear, and the button that creates it. */
  empty: { message: string; action: ReactNode };
  children: (data: T) => ReactNode;
}

function unavailableWording(error: unknown): ScreenWording | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  const { code, details } = error.envelope.error;
  return screenWording(code, details?.dependency);
}

/** FR-005: every data view renders loading, empty, error and unavailable. */
export function DataView<T>({ query, isEmpty, skeleton, empty, children }: DataViewProps<T>) {
  if (query.status === "pending") {
    return <>{skeleton}</>;
  }
  if (query.status === "error") {
    // DC-3: a 403 shows a page naming the role required.
    if (query.error instanceof ApiError && query.error.status === 403) {
      return <NotAllowed />;
    }
    const wording = unavailableWording(query.error);
    if (wording !== null) {
      return <Unavailable wording={wording} />;
    }
    return (
      <div className="flex flex-col items-start gap-3">
        <Callout kind="error">{query.error.message}</Callout>
        <Button
          variant="secondary"
          onClick={() => {
            void query.refetch();
          }}
        >
          Retry
        </Button>
      </div>
    );
  }
  if (isEmpty(query.data)) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-card border border-border bg-surface p-6">
        <p className="m-0 text-text-secondary">{empty.message}</p>
        {empty.action}
      </div>
    );
  }
  return <>{children(query.data)}</>;
}

function Unavailable({ wording }: { wording: ScreenWording }) {
  return (
    <div className="flex flex-col gap-3">
      <Callout kind="caution" lead={wording.headline}>
        {"closing" in wording && wording.closing}
      </Callout>
      {"stillWorks" in wording && (
        <div>
          <p className="m-0 mb-2 font-medium">Still works</p>
          <ul className="m-0 flex list-none flex-col gap-1 p-0">
            {wording.stillWorks.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <CheckCircleIcon size={20} className="text-positive" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
