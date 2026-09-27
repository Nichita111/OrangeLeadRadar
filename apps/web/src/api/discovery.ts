import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useConfig } from "../configContext";
import { client, requireData } from "./client";
import type { Schemas } from "./contract";
import { isRunFinal, runsKeys } from "./runs";

export type DiscoveryCandidate = Schemas["DiscoveryCandidate"];
export type CandidateStatus = Schemas["DiscoveryCandidateStatus"];

/** One query key family for the [Discovery](/architecture/interfaces.md#discovery) family. */
export const discoveryKeys = {
  candidates: (serviceId: string, status: CandidateStatus | undefined, page: number) =>
    ["discovery", "candidates", serviceId, status ?? "ALL", page] as const,
  candidatesRoot: (serviceId: string) => ["discovery", "candidates", serviceId] as const,
  latestRun: (serviceId: string) => [...runsKeys, "latest-discovery", serviceId] as const,
};

/** `API-30`: a service's discovery candidates, ordered by `fit_estimate` descending. */
export function useDiscoveryCandidates(
  serviceId: string,
  status: CandidateStatus | undefined,
  page: number,
) {
  return useQuery({
    queryKey: discoveryKeys.candidates(serviceId, status, page),
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/discovery-candidates", {
            params: { query: { service_id: serviceId, status, page } },
          })
        ).data,
      ),
  });
}

/**
 * `API-34` filtered to `kind=DISCOVERY&service_id=…`, newest first, one row: how the screen finds
 * a running discovery when it opens.
 */
export function useLatestDiscoveryRun(serviceId: string) {
  const { RUN_POLL_INTERVAL_MS } = useConfig();
  return useQuery({
    queryKey: discoveryKeys.latestRun(serviceId),
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/runs", {
            params: { query: { kind: "DISCOVERY", service_id: serviceId, page: 1, page_size: 1 } },
          })
        ).data,
      ),
    refetchInterval: (query) => {
      const latest = query.state.data?.items[0];
      return isRunFinal(latest) || latest === undefined ? false : RUN_POLL_INTERVAL_MS;
    },
  });
}

/** `API-29`: starts (or returns) the service's discovery run, and invalidates the latest-run
 * query so the running callout picks it up. */
export function useStartDiscovery(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      requireData(
        (
          await client.POST("/api/v1/services/{id}/discovery-runs", {
            params: { path: { id: serviceId } },
          })
        ).data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: discoveryKeys.latestRun(serviceId) });
    },
  });
}

function replaceCandidate(
  queryClient: ReturnType<typeof useQueryClient>,
  serviceId: string,
  updated: DiscoveryCandidate,
) {
  queryClient.setQueriesData(
    { queryKey: discoveryKeys.candidatesRoot(serviceId) },
    (page: { items: DiscoveryCandidate[] } | undefined) =>
      page === undefined
        ? page
        : {
            ...page,
            items: page.items.map((item) => (item.id === updated.id ? updated : item)),
          },
  );
}

/** `API-31`: accepts a candidate, marking its row Accepted in place (`FR-142`, G10). */
export function useAcceptCandidate(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, domain }: { id: string; domain?: string }) => {
      const body: Schemas["CandidateDecision"] = domain === undefined ? {} : { domain };
      const account = requireData(
        (
          await client.POST("/api/v1/discovery-candidates/{id}/accept", {
            params: { path: { id } },
            body,
          })
        ).data,
      );
      return { id, account };
    },
    onSuccess: ({ id, account }) => {
      queryClient.setQueriesData(
        { queryKey: discoveryKeys.candidatesRoot(serviceId) },
        (page: { items: DiscoveryCandidate[] } | undefined) =>
          page === undefined
            ? page
            : {
                ...page,
                items: page.items.map((item) =>
                  item.id === id
                    ? { ...item, status: "ACCEPTED" as const, account_id: account.id }
                    : item,
                ),
              },
      );
    },
  });
}

/** `API-32`: rejects a candidate; the row leaves the Pending list once refetched. */
export function useRejectCandidate(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason?: string }) => {
      const body: Schemas["CandidateDecision"] = reason === undefined ? {} : { reason };
      return requireData(
        (
          await client.POST("/api/v1/discovery-candidates/{id}/reject", {
            params: { path: { id } },
            body,
          })
        ).data,
      );
    },
    onSuccess: (updated) => {
      replaceCandidate(queryClient, serviceId, updated);
    },
  });
}
