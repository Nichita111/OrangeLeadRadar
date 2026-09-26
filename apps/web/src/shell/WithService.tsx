import type { ReactNode } from "react";

import type { Schemas } from "../api/contract";
import { Skeleton } from "../components/Skeleton";
import { useServiceSelection } from "./SelectedService";
import { DataView } from "./states/DataView";

/**
 * FR-003, FR-005: a screen of the selected service. Loading, an unavailable list of services and
 * "no active service" are shown here, so the screen inside always has a service.
 */
export function WithService({
  children,
}: {
  children: (service: Schemas["Service"]) => ReactNode;
}) {
  const { isLoading, error, refetch, service } = useServiceSelection();
  const query =
    error !== null
      ? ({ status: "error", error, refetch } as const)
      : isLoading
        ? ({ status: "pending", refetch } as const)
        : ({ status: "success", data: service, refetch } as const);
  return (
    <DataView
      query={query}
      isEmpty={(current) => current === null}
      skeleton={<Skeleton className="h-40 w-full" />}
      empty={{ message: "There is no active service yet.", action: null }}
    >
      {(current) => (current === null ? null : children(current))}
    </DataView>
  );
}
