/** `API-71` and `API-74` ([Industries and markets](/architecture/interfaces.md#industries-and-markets)). */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type Industry = components["schemas"]["Industry"];
export type Market = components["schemas"]["Market"];

/** All statuses: an inactive industry still needs its label. */
export function useIndustries(): UseQueryResult<Industry[]> {
  return useQuery({
    queryKey: ["industries"],
    queryFn: () => apiRequest<Industry[]>("/industries"),
  });
}

export function useMarkets(): UseQueryResult<Market[]> {
  return useQuery({ queryKey: ["markets"], queryFn: () => apiRequest<Market[]>("/markets") });
}
