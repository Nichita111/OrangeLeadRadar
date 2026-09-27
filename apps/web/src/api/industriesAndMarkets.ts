import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";

/** One query key family for [Industries and markets](/architecture/interfaces.md#industries-and-markets). */
export const industriesAndMarketsKeys = {
  industries: ["industries-and-markets", "industries"] as const,
  markets: ["industries-and-markets", "markets"] as const,
};

/** `API-71`: all statuses, since an inactive industry still needs its label. */
export function useIndustries() {
  return useQuery({
    queryKey: industriesAndMarketsKeys.industries,
    queryFn: async () => requireData((await client.GET("/api/v1/industries")).data),
  });
}

/** `API-74`: all statuses. */
export function useMarkets() {
  return useQuery({
    queryKey: industriesAndMarketsKeys.markets,
    queryFn: async () => requireData((await client.GET("/api/v1/markets")).data),
  });
}

/** `API-72`. */
export function useCreateIndustry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["IndustryCreate"]) =>
      requireData((await client.POST("/api/v1/industries", { body })).data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: industriesAndMarketsKeys.industries });
    },
  });
}

/** `API-73`. */
export function useUpdateIndustry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ code, body }: { code: string; body: Schemas["IndustryUpdate"] }) =>
      requireData(
        (await client.PATCH("/api/v1/industries/{code}", { params: { path: { code } }, body }))
          .data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: industriesAndMarketsKeys.industries });
    },
  });
}

/** `API-75`. */
export function useCreateMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["MarketCreate"]) =>
      requireData((await client.POST("/api/v1/markets", { body })).data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: industriesAndMarketsKeys.markets });
    },
  });
}

/** `API-76`. */
export function useUpdateMarket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ code, body }: { code: string; body: Schemas["MarketUpdate"] }) =>
      requireData(
        (await client.PATCH("/api/v1/markets/{code}", { params: { path: { code } }, body })).data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: industriesAndMarketsKeys.markets });
    },
  });
}
