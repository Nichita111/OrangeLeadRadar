import { useQuery } from "@tanstack/react-query";

import { useConfig } from "../configContext";
import { client, requireData } from "./client";
import type { Schemas } from "./contract";

export type Run = Schemas["Run"];

/** One query key family for the interface family Runs and source plug-ins. */
export const runsKeys = ["runs"] as const;

const FINAL_STATUSES: Schemas["PipelineRunStatus"][] = [
  "SUCCEEDED",
  "PARTIAL",
  "FAILED",
  "CANCELLED",
];

/** Whether a run has left `QUEUED`/`RUNNING` for good (`FR-012`). */
export function isRunFinal(run: Run | undefined): boolean {
  return run !== undefined && FINAL_STATUSES.includes(run.status);
}

/**
 * `API-35`. Polls every `RUN_POLL_INTERVAL_MS` while the run is `QUEUED` or `RUNNING`, and stops
 * once it is final (`FR-012`, [ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md)).
 */
export function useRun(runId: string | undefined) {
  const { RUN_POLL_INTERVAL_MS } = useConfig();
  return useQuery({
    queryKey: [...runsKeys, "detail", runId],
    enabled: runId !== undefined,
    queryFn: async () =>
      requireData(
        (await client.GET("/api/v1/runs/{id}", { params: { path: { id: runId ?? "" } } })).data,
      ),
    refetchInterval: (query) => (isRunFinal(query.state.data) ? false : RUN_POLL_INTERVAL_MS),
  });
}

/**
 * `API-34` filtered to `kind=EVALUATION`, newest first, one row: the Quality report's way of
 * finding a running check when it opens (D3).
 */
export function useLatestEvaluationRun() {
  const { RUN_POLL_INTERVAL_MS } = useConfig();
  return useQuery({
    queryKey: [...runsKeys, "latest-evaluation"],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/runs", {
            params: { query: { kind: "EVALUATION", page: 1, page_size: 1 } },
          })
        ).data,
      ),
    refetchInterval: (query) => {
      const latest = query.state.data?.items[0];
      return isRunFinal(latest) || latest === undefined ? false : RUN_POLL_INTERVAL_MS;
    },
  });
}
