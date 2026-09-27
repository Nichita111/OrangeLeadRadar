import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";
import { servicesAndQuestionsKeys } from "./servicesAndQuestions";

/** One query key family for [Scoring](/architecture/interfaces.md#scoring). */
export const scoringKeys = {
  configs: (serviceId: string) => ["scoring", "configs", serviceId] as const,
  config: (id: string) => ["scoring", "config", id] as const,
};

/** `API-15`: newest version first. */
export function useScoringConfigs(serviceId: string | undefined) {
  return useQuery({
    queryKey: scoringKeys.configs(serviceId ?? ""),
    enabled: serviceId !== undefined,
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/services/{id}/scoring-configs", {
            params: { path: { id: serviceId ?? "" } },
          })
        ).data,
      ),
  });
}

/** `API-16`. */
export function useScoringConfig(id: string | undefined) {
  return useQuery({
    queryKey: scoringKeys.config(id ?? ""),
    enabled: id !== undefined,
    queryFn: async () =>
      requireData(
        (await client.GET("/api/v1/scoring-configs/{id}", { params: { path: { id: id ?? "" } } }))
          .data,
      ),
  });
}

async function invalidateScoringAndServices(
  queryClient: ReturnType<typeof useQueryClient>,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["scoring"] }),
    queryClient.invalidateQueries({ queryKey: servicesAndQuestionsKeys.services }),
  ]);
}

/** `API-17`. */
export function useSaveScoringDraft(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["ScoringDraftUpdate"]) =>
      requireData(
        (
          await client.PUT("/api/v1/services/{id}/scoring-configs/draft", {
            params: { path: { id: serviceId } },
            body,
          })
        ).data,
      ),
    onSuccess: async () => {
      await invalidateScoringAndServices(queryClient);
    },
  });
}

/** `API-18`. */
export function useActivateScoringConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Schemas["ActivationRequest"] }) =>
      requireData(
        (
          await client.POST("/api/v1/scoring-configs/{id}/activate", {
            params: { path: { id } },
            body,
          })
        ).data,
      ),
    onSuccess: async () => {
      await invalidateScoringAndServices(queryClient);
    },
  });
}

/** `API-15` then `API-16`: the band thresholds of the active scoring version, or null when none. */
export function useBandThresholds(serviceId: string | undefined) {
  return useQuery({
    queryKey: [...scoringKeys.configs(serviceId ?? ""), "band-thresholds"],
    enabled: serviceId !== undefined,
    queryFn: async () => {
      const summaries = requireData(
        (
          await client.GET("/api/v1/services/{id}/scoring-configs", {
            params: { path: { id: serviceId ?? "" } },
          })
        ).data,
      );
      const active = summaries.find((summary) => summary.status === "ACTIVE");
      if (active === undefined) {
        return null;
      }
      const config = requireData(
        (await client.GET("/api/v1/scoring-configs/{id}", { params: { path: { id: active.id } } }))
          .data,
      );
      return {
        hot_threshold: config.settings.hot_threshold,
        warm_threshold: config.settings.warm_threshold,
      };
    },
  });
}
