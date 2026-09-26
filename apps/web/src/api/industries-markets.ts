/**
 * Query hooks of `API-71` to `API-76` ([Industries and markets]
 * (/architecture/interfaces.md#industries-and-markets)). Two query key families, `["industries",
 * ...]` and `["markets", ...]`, each keyed by the `status` filter so the active-only list an ICP
 * criterion reads never collides with the full list this screen shows.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type Industry = components["schemas"]["Industry"];
export type IndustryCreate = components["schemas"]["IndustryCreate"];
export type IndustryUpdate = components["schemas"]["IndustryUpdate"];
export type IndustryStatus = components["schemas"]["IndustryStatus"];

export type Market = components["schemas"]["Market"];
export type MarketCreate = components["schemas"]["MarketCreate"];
export type MarketUpdate = components["schemas"]["MarketUpdate"];
export type MarketStatus = components["schemas"]["MarketStatus"];

export const industriesQueryKey = (status?: IndustryStatus) =>
  ["industries", status ?? "all"] as const;
export const marketsQueryKey = (status?: MarketStatus) => ["markets", status ?? "all"] as const;

/** `API-71`. */
export function useIndustries(status?: IndustryStatus): UseQueryResult<Industry[]> {
  return useQuery({
    queryKey: industriesQueryKey(status),
    queryFn: () =>
      apiRequest<Industry[]>(`/industries${status !== undefined ? `?status=${status}` : ""}`),
  });
}

export function useCreateIndustry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IndustryCreate) =>
      apiRequest<Industry>("/industries", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["industries"] });
    },
  });
}

export function useUpdateIndustry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, body }: { code: string; body: IndustryUpdate }) =>
      apiRequest<Industry>(`/industries/${code}`, { method: "PATCH", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["industries"] });
    },
  });
}

/** `API-74`. */
export function useMarkets(status?: MarketStatus): UseQueryResult<Market[]> {
  return useQuery({
    queryKey: marketsQueryKey(status),
    queryFn: () =>
      apiRequest<Market[]>(`/markets${status !== undefined ? `?status=${status}` : ""}`),
  });
}

export function useCreateMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: MarketCreate) => apiRequest<Market>("/markets", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["markets"] });
    },
  });
}

export function useUpdateMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, body }: { code: string; body: MarketUpdate }) =>
      apiRequest<Market>(`/markets/${code}`, { method: "PATCH", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["markets"] });
    },
  });
}
