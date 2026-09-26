import { useQuery } from "@tanstack/react-query";

import { apiClient, unwrap } from "./client";

export const alertKeys = {
  unreadCount: (serviceId: string) => ["alerts", "unread-count", serviceId] as const,
};

/**
 * `API-48` (`FR-002`, `FR-013`): the unread-alert count of a service, read from `total` with
 * `unread=true`; the client never sends `page_size`. Refetches every `pollIntervalMs` and when
 * the window regains focus.
 */
export function useUnreadAlertCount(serviceId: string | undefined, pollIntervalMs: number) {
  return useQuery({
    queryKey: alertKeys.unreadCount(serviceId ?? ""),
    queryFn: async () => {
      const page = unwrap(
        await apiClient.GET("/api/v1/alerts", {
          params: { query: { service_id: serviceId ?? "", unread: true } },
        }),
      );
      return page.total;
    },
    enabled: serviceId !== undefined,
    refetchInterval: pollIntervalMs,
    refetchOnWindowFocus: true,
  });
}
