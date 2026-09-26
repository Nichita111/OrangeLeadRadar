/**
 * Query hook of `API-71` ([Industries and markets](/architecture/interfaces.md)), read-only here:
 * this task only lists industries for the [Accounts](/features/accounts-and-discovery.md#accounts)
 * filter and the [Account profile](/features/accounts-and-discovery.md#account-profile) field.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type Industry = components["schemas"]["Industry"];
export type IndustryStatus = components["schemas"]["IndustryStatus"];

/** `API-71`, defaulting to `ACTIVE` so a screen offers only industries a user may pick. */
export function useIndustries(status: IndustryStatus = "ACTIVE"): UseQueryResult<Industry[]> {
  return useQuery({
    queryKey: ["industries", status] as const,
    queryFn: () => apiRequest<Industry[]>(`/industries?status=${status}`),
  });
}
