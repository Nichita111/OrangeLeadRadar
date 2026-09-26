/**
 * Query hooks of `API-15` to `API-17` ([Scoring](/architecture/interfaces.md#scoring)); `API-18`
 * (activate) and `API-19` (preview) are owned by a later task ([S-CFG-04]
 * (/requirements/system.md), [S-CFG-06](/requirements/system.md)). One query key family per
 * service, `["scoring-configs", serviceId]`, plus `["scoring-config", id]` for one version's
 * settings.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type ScoringConfigSummary = components["schemas"]["ScoringConfigSummaryModel"];
export type ScoringConfig = components["schemas"]["ScoringConfigModel"];
export type ScoringConfigStatus = components["schemas"]["ScoringConfigStatus"];
export type ScoringDraftUpdate = components["schemas"]["ScoringDraftUpdate"];
export type ScoringSettingsDocument = components["schemas"]["ScoringSettingsDocument"];
export type ICPCriterion = components["schemas"]["ICPCriterion"];
export type ICPCriterionKind = components["schemas"]["ICPCriterionKind"];
export type QuestionSetting = components["schemas"]["QuestionSetting"];
export type Disqualifier = components["schemas"]["Disqualifier"];
export type DisqualifierKind = components["schemas"]["DisqualifierKind"];
export type WeightLevel = components["schemas"]["WeightLevel"];
export type FindingStrength = components["schemas"]["FindingStrength"];

export const scoringConfigsQueryKey = (serviceId: string) =>
  ["scoring-configs", serviceId] as const;
export const scoringConfigQueryKey = (id: string) => ["scoring-config", id] as const;

/** `API-15`. */
export function useScoringConfigs(serviceId: string): UseQueryResult<ScoringConfigSummary[]> {
  return useQuery({
    queryKey: scoringConfigsQueryKey(serviceId),
    queryFn: () => apiRequest<ScoringConfigSummary[]>(`/services/${serviceId}/scoring-configs`),
  });
}

/** `API-16`. */
export function useScoringConfig(id: string | null): UseQueryResult<ScoringConfig> {
  return useQuery({
    queryKey: scoringConfigQueryKey(id ?? ""),
    queryFn: () => apiRequest<ScoringConfig>(`/scoring-configs/${id ?? ""}`),
    enabled: id !== null,
  });
}

export function useSaveScoringDraft(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ScoringDraftUpdate) =>
      apiRequest<ScoringConfig>(`/services/${serviceId}/scoring-configs/draft`, {
        method: "PUT",
        body,
      }),
    onSuccess: (config) => {
      void queryClient.invalidateQueries({ queryKey: scoringConfigsQueryKey(serviceId) });
      void queryClient.invalidateQueries({ queryKey: ["services", serviceId] });
      queryClient.setQueryData(scoringConfigQueryKey(config.id), config);
    },
  });
}
