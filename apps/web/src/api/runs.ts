import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useConfig } from "../configContext";
import { client, requireData } from "./client";
import type { Schemas } from "./contract";

export type Run = Schemas["Run"];
export type SourcePlugin = Schemas["SourcePlugin"];

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
 * The first `SCORING_ACTIVATION` run of `runs`, or undefined when there is none (G1 b): an
 * activation's own `RESCORE` run among account rescores of the same service, which share `kind`
 * and `service_id`, so `trigger` is filtered on the client.
 */
export function activationRescore(runs: readonly Run[]): Run | undefined {
  return runs.find((run) => run.trigger === "SCORING_ACTIVATION");
}

/**
 * `API-34` filtered to `kind=RESCORE&service_id=…`, newest first, read once after `API-18`
 * answers (G1 b, `FR-036`): the run the Activate dialog then polls through `useRun`.
 */
export function useActivationRescore(serviceId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: [...runsKeys, "activation-rescore", serviceId],
    enabled: enabled && serviceId !== undefined,
    queryFn: async () =>
      activationRescore(
        requireData(
          (
            await client.GET("/api/v1/runs", {
              params: { query: { kind: "RESCORE", service_id: serviceId ?? "" } },
            })
          ).data,
        ).items,
      ),
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

const sourcePluginsKey = [...runsKeys, "source-plugins"] as const;

/** `API-37`: every source plug-in, in the api's order (Admin only). */
export function useSourcePlugins() {
  return useQuery({
    queryKey: sourcePluginsKey,
    queryFn: async () => requireData((await client.GET("/api/v1/source-plugins")).data),
  });
}

/**
 * `API-38`: saves the switch or a limit of one plug-in. On success the returned plug-in replaces
 * its entry in the `source-plugins` list cache; no other run query is invalidated.
 */
export function useUpdateSourcePlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      code,
      body,
    }: {
      code: Schemas["SourcePluginCode"];
      body: Schemas["SourcePluginUpdate"];
    }) =>
      requireData(
        (await client.PATCH("/api/v1/source-plugins/{code}", { params: { path: { code } }, body }))
          .data,
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(sourcePluginsKey, (plugins: SourcePlugin[] | undefined) =>
        plugins?.map((plugin) => (plugin.code === updated.code ? updated : plugin)),
      );
    },
  });
}
