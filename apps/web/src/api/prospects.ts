/**
 * Query hooks of `API-39` to `API-45` ([Prospects and evidence]
 * (/architecture/interfaces.md#prospects-and-evidence)). One query key family, `["prospects", ...]`.
 * The only module that imports the pending types: when the api declares these contracts it
 * points at `schema.gen.ts` instead.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, apiRequest } from "./client";
import type { components as pending, operations } from "./pending/schema.gen";
import type { components } from "./schema.gen";

export type ProspectPage = pending["schemas"]["ProspectPage"];
export type ProspectRow = pending["schemas"]["ProspectRow"];
export type ScoreView = pending["schemas"]["ScoreView"];
export type ScoreBreakdown = pending["schemas"]["ScoreBreakdown"];
export type EvidenceView = pending["schemas"]["EvidenceView"];
export type Override = pending["schemas"]["Override"];
export type OverrideCreate = pending["schemas"]["OverrideCreate"];
export type Standing = pending["schemas"]["Standing"];
export type Band = pending["schemas"]["Band"];
export type FindingView = components["schemas"]["FindingView"];
export type FindingStatus = components["schemas"]["FindingStatus"];

export type ProspectSort = NonNullable<
  NonNullable<operations["list_prospects"]["parameters"]["query"]>["sort"]
>;

export const prospectsQueryKey = ["prospects"] as const;

export interface ProspectQuery {
  page?: number | undefined;
  standing?: Standing | undefined;
  band?: Band | undefined;
  country_code?: string | undefined;
  industry?: string | undefined;
  q?: string | undefined;
  sort?: ProspectSort | undefined;
}

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.append(name, String(value));
    }
  }
  const text = search.toString();
  return text.length > 0 ? `?${text}` : "";
}

/** `API-39`: the api ranks; the client never sorts. */
export function useProspects(
  serviceId: string | undefined,
  query: ProspectQuery,
): UseQueryResult<ProspectPage> {
  return useQuery({
    queryKey: [...prospectsQueryKey, "list", serviceId, query],
    queryFn: () =>
      apiRequest<ProspectPage>(
        `/services/${serviceId ?? ""}/prospects${queryString({ ...query })}`,
      ),
    enabled: serviceId !== undefined,
  });
}

/** `API-40`: a `404` means the account has no score for the service yet, not an error. */
export function useScore(
  accountId: string,
  serviceId: string | undefined,
): UseQueryResult<ScoreView | null> {
  return useQuery({
    queryKey: [...prospectsQueryKey, "score", accountId, serviceId],
    queryFn: async () => {
      try {
        return await apiRequest<ScoreView>(`/accounts/${accountId}/scores/${serviceId ?? ""}`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
    enabled: serviceId !== undefined,
  });
}

/** `API-42`. */
export function useFindings(
  accountId: string,
  serviceId: string | undefined,
  status: FindingStatus,
): UseQueryResult<FindingView[]> {
  return useQuery({
    queryKey: [...prospectsQueryKey, "findings", accountId, serviceId, status],
    queryFn: () =>
      apiRequest<FindingView[]>(
        `/accounts/${accountId}/findings${queryString({ service_id: serviceId, status })}`,
      ),
    enabled: serviceId !== undefined,
  });
}

/** `API-43`: fetched only once a signal's evidence is opened. */
export function useEvidence(findingId: string | null): UseQueryResult<EvidenceView> {
  return useQuery({
    queryKey: [...prospectsQueryKey, "evidence", findingId],
    queryFn: () => apiRequest<EvidenceView>(`/findings/${findingId ?? ""}/evidence`),
    enabled: findingId !== null,
  });
}

/** `API-44`. */
export function useAddOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      accountId,
      serviceId,
      body,
    }: {
      accountId: string;
      serviceId: string;
      body: OverrideCreate;
    }) =>
      apiRequest<Override>(`/accounts/${accountId}/scores/${serviceId}/overrides`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: prospectsQueryKey });
    },
  });
}

/** `API-45`. */
export function useRevokeOverride() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (overrideId: string) =>
      apiRequest<Override>(`/overrides/${overrideId}/revoke`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: prospectsQueryKey });
    },
  });
}
