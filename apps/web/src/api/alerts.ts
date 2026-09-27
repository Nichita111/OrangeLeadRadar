import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";

export type AlertView = Schemas["AlertView"];

/** One query key family for the Alerts screen. */
export const alertsKeys = ["alerts"] as const;

/** `API-48`: the service's alerts, newest first; unread only unless `unread` is false. */
export function useAlerts(serviceId: string, unread: boolean) {
  return useQuery({
    queryKey: [...alertsKeys, serviceId, unread],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/alerts", {
            params: { query: { service_id: serviceId, unread } },
          })
        ).data,
      ),
  });
}

/** `API-49`: marks an alert read for the whole team (`FR-077`). */
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (alertId: string) =>
      requireData(
        (
          await client.POST("/api/v1/alerts/{id}/acknowledge", {
            params: { path: { id: alertId } },
          })
        ).data,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alertsKeys }),
  });
}
