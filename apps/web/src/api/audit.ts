import { useQuery } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";

export type AuditEntry = Schemas["AuditEntry"];
export type AuditEventKind = Schemas["AuditEventKind"];
export type AuditAction = Schemas["AuditAction"];

/** One query key family for the interface family Audit and health. */
export const auditKeys = ["audit"] as const;

export interface AuditFilters {
  kinds: AuditEventKind[];
  action: AuditAction | undefined;
  actor_id: string;
  entity_id: string;
  run_id: string;
  from: string;
  to: string;
  page: number;
}

/** `API-60`: newest first; the api filters and pages, the client never sorts. */
export function useAuditLog(filters: AuditFilters) {
  return useQuery({
    queryKey: [...auditKeys, filters],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/audit", {
            params: {
              query: {
                page: filters.page,
                ...(filters.kinds.length === 0 ? {} : { kind: filters.kinds }),
                ...(filters.action === undefined ? {} : { action: filters.action }),
                ...(filters.actor_id === "" ? {} : { actor_id: filters.actor_id }),
                ...(filters.entity_id === "" ? {} : { entity_id: filters.entity_id }),
                ...(filters.run_id === "" ? {} : { run_id: filters.run_id }),
                ...(filters.from === "" ? {} : { from: filters.from }),
                ...(filters.to === "" ? {} : { to: filters.to }),
              },
            },
          })
        ).data,
      ),
  });
}
