import { useQuery } from "@tanstack/react-query";

import { client, requireData } from "./client";

/** One query key family for the read-only reference data the Prospects screens show. */
export const referenceDataKeys = ["reference-data"] as const;

/** `API-07`. */
export function useServices() {
  return useQuery({
    queryKey: [...referenceDataKeys, "services"],
    queryFn: async () => requireData((await client.GET("/api/v1/services")).data),
  });
}

/** `API-71`: all statuses, since an inactive industry still needs its label. */
export function useIndustries() {
  return useQuery({
    queryKey: [...referenceDataKeys, "industries"],
    queryFn: async () => requireData((await client.GET("/api/v1/industries")).data),
  });
}

/** `API-74`. */
export function useMarkets() {
  return useQuery({
    queryKey: [...referenceDataKeys, "markets"],
    queryFn: async () => requireData((await client.GET("/api/v1/markets")).data),
  });
}

/** `API-23`. */
export function useAccount(id: string) {
  return useQuery({
    queryKey: [...referenceDataKeys, "account", id],
    queryFn: async () =>
      requireData((await client.GET("/api/v1/accounts/{id}", { params: { path: { id } } })).data),
  });
}

export interface BandThresholds {
  hot_threshold: number;
  warm_threshold: number;
}

function isThresholds(
  value: Record<string, unknown>,
): value is Record<string, unknown> & BandThresholds {
  return typeof value["hot_threshold"] === "number" && typeof value["warm_threshold"] === "number";
}

/** `API-15` then `API-16`: the band thresholds of the active scoring version, or null when none. */
export function useBandThresholds(serviceId: string | undefined) {
  return useQuery({
    queryKey: [...referenceDataKeys, "band-thresholds", serviceId],
    enabled: serviceId !== undefined,
    queryFn: async (): Promise<BandThresholds | null> => {
      const id = serviceId ?? "";
      const summaries = requireData(
        (await client.GET("/api/v1/services/{id}/scoring-configs", { params: { path: { id } } }))
          .data,
      );
      const active = summaries.find((summary) => summary.status === "ACTIVE");
      if (active === undefined) {
        return null;
      }
      const config = requireData(
        (await client.GET("/api/v1/scoring-configs/{id}", { params: { path: { id: active.id } } }))
          .data,
      );
      return isThresholds(config.settings)
        ? {
            hot_threshold: config.settings.hot_threshold,
            warm_threshold: config.settings.warm_threshold,
          }
        : null;
    },
  });
}
