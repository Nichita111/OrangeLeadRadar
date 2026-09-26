import { useQuery } from "@tanstack/react-query";

import { apiClient, unwrap } from "./client";

export const serviceKeys = {
  list: ["services"] as const,
};

/** `API-07` (`FR-003`): every service the caller can see, Admin and Sales alike. */
export function useServices() {
  return useQuery({
    queryKey: serviceKeys.list,
    queryFn: async () => unwrap(await apiClient.GET("/api/v1/services")),
  });
}
