import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";
import { runsKeys } from "./runs";

export type LabelQueue = Schemas["LabelQueue"];
export type LabelTask = Schemas["LabelTask"];
export type LabelCreate = Schemas["LabelCreate"];
export type EvaluationItem = Schemas["EvaluationItem"];
export type EvaluationResultSummary = Schemas["EvaluationResultSummary"];
export type EvaluationResult = Schemas["EvaluationResult"];
export type Impact = Schemas["Impact"];

/** One query key family for the interface family Evaluation. */
export const evaluationKeys = ["evaluation"] as const;

/** `API-50`: the label queue for the header's selected service (`FR-003`). */
export function useLabelQueue(serviceId: string | undefined) {
  return useQuery({
    queryKey: [...evaluationKeys, "label-queue", serviceId],
    enabled: serviceId !== undefined,
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/evaluation/label-queue", {
            params: { query: { service_id: serviceId ?? "" } },
          })
        ).data,
      ),
  });
}

/** `API-51`. */
export function useSubmitLabel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: LabelCreate) =>
      requireData((await client.POST("/api/v1/evaluation/items", { body })).data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: [...evaluationKeys, "label-queue"] });
    },
  });
}

/** `API-53`: requests a quality check; `202` with a new run or `200` with the one already
 * queued or running (D2). */
export function useRequestQualityCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => requireData((await client.POST("/api/v1/evaluation/runs")).data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: runsKeys });
    },
  });
}

/** `API-54`: newest first. */
export function useEvaluationResults() {
  return useQuery({
    queryKey: [...evaluationKeys, "results"],
    queryFn: async () => requireData((await client.GET("/api/v1/evaluation/results")).data),
  });
}

/** `API-55`. */
export function useEvaluationResult(runId: string | undefined) {
  return useQuery({
    queryKey: [...evaluationKeys, "result", runId],
    enabled: runId !== undefined,
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/evaluation/results/{run_id}", {
            params: { path: { run_id: runId ?? "" } },
          })
        ).data,
      ),
  });
}

/** Invalidates the results and the latest-run views once a quality check finishes (`FR-082`). */
export function useInvalidateEvaluationResults() {
  const queryClient = useQueryClient();
  return async () => {
    await queryClient.invalidateQueries({ queryKey: evaluationKeys });
  };
}

/** `API-77`: computed on read, writes nothing. */
export function useImpact() {
  return useQuery({
    queryKey: [...evaluationKeys, "impact"],
    queryFn: async () => requireData((await client.GET("/api/v1/impact")).data),
  });
}
