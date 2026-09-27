import { useQuery } from "@tanstack/react-query";

import { client, requireData } from "./client";

/** One query key family for the read-only reference data the Prospects screens show. */
export const referenceDataKeys = ["reference-data"] as const;

/** `API-23`. */
export function useAccount(id: string) {
  return useQuery({
    queryKey: [...referenceDataKeys, "account", id],
    queryFn: async () =>
      requireData((await client.GET("/api/v1/accounts/{id}", { params: { path: { id } } })).data),
  });
}
