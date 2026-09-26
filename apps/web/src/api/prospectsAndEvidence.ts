import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, client, requireData } from "./client";
import type { Schemas, paths } from "./contract";

export type ProspectRow = Schemas["ProspectRow"];
export type ScoreView = Schemas["ScoreView"];
export type Override = Schemas["Override"];
export type Standing = Schemas["Standing"];
export type Band = Schemas["Band"];
export type FindingView = Schemas["FindingView"];
export type FindingStatus = Schemas["FindingStatus"];
export type ProspectSort = NonNullable<
  NonNullable<paths["/api/v1/services/{id}/prospects"]["get"]["parameters"]["query"]>["sort"]
>;

/** One query key family for the interface family Prospects and evidence. */
export const prospectsAndEvidenceKeys = ["prospects-and-evidence"] as const;

export interface ProspectFilters {
  page: number;
  standing: Standing;
  band: Band | undefined;
  country_code: string;
  industry: string;
  q: string;
  sort: ProspectSort;
}

/** `API-39`: the api ranks; the client never sorts. */
export function useProspects(serviceId: string | undefined, filters: ProspectFilters) {
  return useQuery({
    queryKey: [...prospectsAndEvidenceKeys, "list", serviceId, filters],
    enabled: serviceId !== undefined,
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/services/{id}/prospects", {
            params: {
              path: { id: serviceId ?? "" },
              query: {
                page: filters.page,
                standing: filters.standing,
                sort: filters.sort,
                ...(filters.band === undefined ? {} : { band: [filters.band] }),
                ...(filters.country_code === "" ? {} : { country_code: [filters.country_code] }),
                ...(filters.industry === "" ? {} : { industry: [filters.industry] }),
                ...(filters.q === "" ? {} : { q: filters.q }),
              },
            },
          })
        ).data,
      ),
  });
}

/** `API-40`: a `404` means the account has no score for the service yet, not an error. */
export function useScore(accountId: string, serviceId: string | undefined) {
  return useQuery({
    queryKey: [...prospectsAndEvidenceKeys, "score", accountId, serviceId],
    enabled: serviceId !== undefined,
    queryFn: async (): Promise<ScoreView | null> => {
      try {
        return requireData(
          (
            await client.GET("/api/v1/accounts/{id}/scores/{service_id}", {
              params: { path: { id: accountId, service_id: serviceId ?? "" } },
            })
          ).data,
        );
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
  });
}

/** `API-42`. */
export function useFindings(
  accountId: string,
  serviceId: string | undefined,
  status: FindingStatus,
) {
  return useQuery({
    queryKey: [...prospectsAndEvidenceKeys, "findings", accountId, serviceId, status],
    enabled: serviceId !== undefined,
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/accounts/{id}/findings", {
            params: {
              path: { id: accountId },
              query: { ...(serviceId === undefined ? {} : { service_id: serviceId }), status },
            },
          })
        ).data,
      ),
  });
}

/** `API-43`: fetched only once a signal's evidence is opened. */
export function useEvidence(findingId: string) {
  return useQuery({
    queryKey: [...prospectsAndEvidenceKeys, "evidence", findingId],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/findings/{id}/evidence", {
            params: { path: { id: findingId } },
          })
        ).data,
      ),
  });
}

/** `API-44`. */
export function useAddOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      accountId,
      serviceId,
      body,
    }: {
      accountId: string;
      serviceId: string;
      body: Schemas["OverrideCreate"];
    }) =>
      requireData(
        (
          await client.POST("/api/v1/accounts/{id}/scores/{service_id}/overrides", {
            params: { path: { id: accountId, service_id: serviceId } },
            body,
          })
        ).data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: prospectsAndEvidenceKeys });
    },
  });
}

/** `API-45`. */
export function useRevokeOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (overrideId: string) =>
      requireData(
        (
          await client.POST("/api/v1/overrides/{id}/revoke", {
            params: { path: { id: overrideId } },
          })
        ).data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: prospectsAndEvidenceKeys });
    },
  });
}
