/**
 * Query hooks of [Audit and health](/architecture/interfaces.md#audit-and-health) (`API-60`).
 * One query key family, `["audit", ...]`.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type AuditEntry = components["schemas"]["AuditEntry"];
export type AuditEntryPage = components["schemas"]["Page_AuditEntry_"];
export type AuditEventKind = components["schemas"]["AuditEventKind"];
export type AuditAction = components["schemas"]["AuditAction"];

export interface AuditFilter {
  kind?: AuditEventKind[];
  action?: AuditAction;
  actor_id?: string;
  entity_id?: string;
  run_id?: string;
  from?: string;
  to?: string;
  page?: number;
}

function auditQueryString(filter: AuditFilter): string {
  const params = new URLSearchParams();
  for (const kind of filter.kind ?? []) {
    params.append("kind", kind);
  }
  if (filter.action !== undefined) {
    params.set("action", filter.action);
  }
  if (filter.actor_id !== undefined && filter.actor_id.length > 0) {
    params.set("actor_id", filter.actor_id);
  }
  if (filter.entity_id !== undefined && filter.entity_id.length > 0) {
    params.set("entity_id", filter.entity_id);
  }
  if (filter.run_id !== undefined && filter.run_id.length > 0) {
    params.set("run_id", filter.run_id);
  }
  if (filter.from !== undefined && filter.from.length > 0) {
    params.set("from", filter.from);
  }
  if (filter.to !== undefined && filter.to.length > 0) {
    params.set("to", filter.to);
  }
  if (filter.page !== undefined) {
    params.set("page", String(filter.page));
  }
  const qs = params.toString();
  return qs.length > 0 ? `?${qs}` : "";
}

/** `API-60`: newest first, filtered by kind, action, user, entity, run and date range. */
export function useAuditLog(filter: AuditFilter): UseQueryResult<AuditEntryPage> {
  return useQuery({
    queryKey: ["audit", filter] as const,
    queryFn: () => apiRequest<AuditEntryPage>(`/audit${auditQueryString(filter)}`),
  });
}
