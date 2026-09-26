import { useQuery } from "@tanstack/react-query";

import { apiClient, unwrap } from "./client";
import type { components } from "./schema.gen";

type RunStatus = components["schemas"]["PipelineRunStatus"];

const FINAL_STATUSES = new Set<RunStatus>(["SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"]);

export const runKeys = {
  detail: (id: string) => ["runs", id] as const,
};

/**
 * `API-35` (`FR-012`, [ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md)): polls
 * every `pollIntervalMs` while the run is `QUEUED` or `RUNNING`, and stops once it is final.
 */
export function useRun(id: string, pollIntervalMs: number) {
  return useQuery({
    queryKey: runKeys.detail(id),
    queryFn: async () =>
      unwrap(await apiClient.GET("/api/v1/runs/{id}", { params: { path: { id } } })),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && FINAL_STATUSES.has(status) ? false : pollIntervalMs;
    },
  });
}
