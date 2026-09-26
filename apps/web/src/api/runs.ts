/**
 * Query hooks of [Runs and source plug-ins](/architecture/interfaces.md#runs-and-source-plug-ins)
 * (`API-34` to `API-36`; `API-33` starts a refresh from Account detail, `API-37`/`API-38` are the
 * Source plug-ins screen — neither is this task's scope). One query key family, `["runs", ...]`.
 * Polling follows [Polling](/architecture/services/frontend.md#polling) (`FR-012`, `ADR-13`): the
 * caller passes `RUN_POLL_INTERVAL_MS` from the [runtime config](./config.ts) as `pollMs`.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type Run = components["schemas"]["Run"];
export type RunPage = components["schemas"]["Page_Run_"];
export type RunError = components["schemas"]["RunError"];
export type PipelineRunKind = components["schemas"]["PipelineRunKind"];
export type PipelineRunStatus = components["schemas"]["PipelineRunStatus"];
export type PipelineRunStage = components["schemas"]["PipelineRunStage"];
export type PipelineRunTrigger = components["schemas"]["PipelineRunTrigger"];

export interface RunsFilter {
  kind?: PipelineRunKind;
  status?: PipelineRunStatus;
  account_id?: string;
  page?: number;
}

/** [`pipeline_run`](/architecture/sql-store.md#pipeline_run) `status`: still open, so `FR-012`
 * keeps polling it. */
export function isRunLive(status: PipelineRunStatus): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function runsQueryString(filter: RunsFilter): string {
  const params = new URLSearchParams();
  if (filter.kind !== undefined) {
    params.set("kind", filter.kind);
  }
  if (filter.status !== undefined) {
    params.set("status", filter.status);
  }
  if (filter.account_id !== undefined && filter.account_id.length > 0) {
    params.set("account_id", filter.account_id);
  }
  if (filter.page !== undefined) {
    params.set("page", String(filter.page));
  }
  const qs = params.toString();
  return qs.length > 0 ? `?${qs}` : "";
}

/** `API-34`. Polls while the page it fetched holds a live run, per `FR-012`; each item is then
 * refetched individually by [`useRun`](#userun) once selected, for the exact contract the
 * requirement names. */
export function useRuns(filter: RunsFilter, pollMs: number): UseQueryResult<RunPage> {
  return useQuery({
    queryKey: ["runs", filter] as const,
    queryFn: () => apiRequest<RunPage>(`/runs${runsQueryString(filter)}`),
    refetchInterval: (query) => {
      const page = query.state.data;
      const hasLiveRun = page?.items.some((run) => isRunLive(run.status)) ?? false;
      return hasLiveRun ? pollMs : false;
    },
  });
}

/** `API-35`, polled every `RUN_POLL_INTERVAL_MS` while the run is queued or running (`FR-012`,
 * [ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md)). */
export function useRun(id: string | undefined, pollMs: number): UseQueryResult<Run> {
  return useQuery({
    queryKey: ["runs", "detail", id] as const,
    queryFn: () => apiRequest<Run>(`/runs/${id ?? ""}`),
    enabled: id !== undefined,
    refetchInterval: (query) =>
      query.state.data && isRunLive(query.state.data.status) ? pollMs : false,
  });
}

/** `API-36`. */
export function useCancelRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<Run>(`/runs/${id}/cancel`, { method: "POST" }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.setQueryData(["runs", "detail", result.id], result);
    },
  });
}
