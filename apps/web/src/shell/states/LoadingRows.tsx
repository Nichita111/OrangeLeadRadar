import type { ReactElement } from "react";

import { Skeleton } from "../../components/ui/skeleton";

/** `FR-118`: skeleton shapes the size of the rows they stand in for, so the layout does not
 * move when the data arrives. */
export function LoadingRows({ rows = 3 }: { rows?: number }): ReactElement {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-2">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-12 w-full" />
      ))}
    </div>
  );
}
