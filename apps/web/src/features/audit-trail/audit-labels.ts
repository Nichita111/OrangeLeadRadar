/**
 * `FR-098`: the one-line subject an [Audit log](/features/audit-trail.md#audit-log) row shows,
 * built from its entity and payload as [Audit actions](/architecture/sql-store.md#audit-actions)
 * states them; an `AI_CALL` line shows role, provider or model, prompt version, cost, latency
 * and outcome instead. The Action column already names the action, so the subject never repeats
 * it.
 */
import { enumLabel as titleCaseEnum, strengthLabel } from "../../shell/format";
import type { AuditAction, AuditEntry, AuditEventKind } from "../../api/audit";

/** `FR-153`: the segmented control's "Changes" option is every kind but `AI_CALL`. */
export const CHANGE_KINDS: AuditEventKind[] = [
  "AUTH",
  "USER",
  "CONFIG",
  "ACCOUNT",
  "CONTACT",
  "RUN",
  "OVERRIDE",
  "FEEDBACK",
  "OUTREACH",
  "CRM",
];

type Payload = Record<string, unknown>;

function str(payload: Payload, key: string): string | undefined {
  const value = payload[key];
  return typeof value === "string" ? value : undefined;
}

function num(payload: Payload, key: string): number | undefined {
  const value = payload[key];
  return typeof value === "number" ? value : undefined;
}

/** The field names of a "changed fields" payload, whichever of the two shapes [Audit actions]
 * (/architecture/sql-store.md#audit-actions) uses: an object keyed by field name, or (`CONTACT_UPDATED`,
 * `DRAFT_UPDATED`) an array of field names. */
function changedFieldNames(payload: Payload | unknown[]): string {
  const names = Array.isArray(payload)
    ? payload.filter((value): value is string => typeof value === "string")
    : Object.keys(payload);
  return names.length > 0 ? names.join(", ") : "no fields";
}

function aiCallSubject(payload: Payload): string {
  const role = str(payload, "ai_role");
  const provider = str(payload, "provider");
  const model = str(payload, "model");
  const promptVersion = str(payload, "prompt_version");
  const costEur = num(payload, "cost_eur");
  const latencyMs = num(payload, "latency_ms");
  const outcome = str(payload, "outcome");
  return [
    role,
    model ?? provider,
    promptVersion,
    costEur !== undefined ? `€${costEur.toFixed(3)}` : undefined,
    latencyMs !== undefined ? `${(latencyMs / 1000).toFixed(1)} s` : undefined,
    outcome,
  ]
    .filter((part): part is string => part !== undefined && part.length > 0)
    .join(" · ");
}

/** One builder per action of the closed [Audit actions]
 * (/architecture/sql-store.md#audit-actions) vocabulary; the `Record` over `AuditAction` keeps
 * every action covered. */
const SUBJECT_BUILDERS: Record<AuditAction, (payload: Payload) => string> = {
  LOGIN_SUCCEEDED: () => "—",
  LOGIN_FAILED: (payload) => titleCaseEnum(str(payload, "reason") ?? "—"),
  LOGOUT: () => "—",
  USER_CREATED: (payload) => titleCaseEnum(str(payload, "role") ?? "—"),
  USER_UPDATED: (payload) => changedFieldNames(payload),
  SERVICE_CREATED: (payload) => str(payload, "code") ?? "—",
  SERVICE_UPDATED: (payload) => changedFieldNames(payload),
  INDUSTRY_CREATED: (payload) => str(payload, "code") ?? "—",
  INDUSTRY_UPDATED: (payload) => changedFieldNames(payload),
  MARKET_CREATED: (payload) => {
    const codes = payload.country_codes;
    const countries = Array.isArray(codes) ? codes.join(", ") : undefined;
    return [str(payload, "code"), countries].filter(Boolean).join(" · ") || "—";
  },
  MARKET_UPDATED: (payload) => changedFieldNames(payload),
  QUESTION_CREATED: (payload) => {
    const revision = num(payload, "revision");
    return [str(payload, "key"), revision !== undefined ? `rev ${String(revision)}` : undefined]
      .filter(Boolean)
      .join(" · ");
  },
  QUESTION_UPDATED: (payload) => changedFieldNames(payload),
  SCORING_DRAFT_SAVED: (payload) => {
    const version = num(payload, "version");
    return version !== undefined ? `v${String(version)}` : "—";
  },
  SCORING_ACTIVATED: (payload) => {
    const version = num(payload, "version");
    const previous = num(payload, "previous_version");
    const note = str(payload, "change_note");
    const versions = [
      version !== undefined ? `v${String(version)}` : undefined,
      previous !== undefined ? `was v${String(previous)}` : undefined,
    ]
      .filter(Boolean)
      .join(", ");
    return [versions, note !== undefined ? `"${note}"` : undefined].filter(Boolean).join(" · ");
  },
  PLUGIN_UPDATED: (payload) => changedFieldNames(payload),
  ACCOUNT_CREATED: (payload) =>
    [str(payload, "domain"), str(payload, "origin")].filter(Boolean).join(" · "),
  ACCOUNT_UPDATED: (payload) => changedFieldNames(payload),
  ACCOUNTS_IMPORTED: (payload) => {
    const rows = num(payload, "rows") ?? 0;
    const created = num(payload, "created") ?? 0;
    const updated = num(payload, "updated") ?? 0;
    const duplicates = num(payload, "duplicates") ?? 0;
    const invalid = num(payload, "invalid") ?? 0;
    return `${String(rows)} rows · ${String(created)} created, ${String(updated)} updated, ${String(duplicates)} duplicates, ${String(invalid)} invalid`;
  },
  CANDIDATE_ACCEPTED: () => "Accepted as an account",
  CANDIDATE_REJECTED: (payload) => titleCaseEnum(str(payload, "reason") ?? "—"),
  CONTACT_CREATED: (payload) => titleCaseEnum(str(payload, "persona") ?? "—"),
  CONTACT_UPDATED: (payload) => changedFieldNames(payload),
  CONTACT_ERASED: (payload) => titleCaseEnum(str(payload, "reason") ?? "—"),
  RUN_REQUESTED: (payload) =>
    [str(payload, "kind"), str(payload, "trigger")]
      .filter(Boolean)
      .map((value) => titleCaseEnum(value ?? ""))
      .join(" · "),
  RUN_FINISHED: (payload) => titleCaseEnum(str(payload, "status") ?? "—"),
  RUN_CANCELLED: () => "—",
  OVERRIDE_CREATED: (payload) =>
    [str(payload, "rule_key"), str(payload, "note")].filter(Boolean).join(" · "),
  OVERRIDE_REVOKED: (payload) => str(payload, "rule_key") ?? "—",
  LEAD_FEEDBACK_GIVEN: (payload) => titleCaseEnum(str(payload, "verdict") ?? "—"),
  FINDING_FEEDBACK_GIVEN: (payload) => titleCaseEnum(str(payload, "verdict") ?? "—"),
  ITEM_LABELLED: (payload) => strengthLabel(str(payload, "expected_strength") ?? "—"),
  DRAFT_CREATED: (payload) => {
    const channel = str(payload, "channel");
    const findingIds = payload.finding_ids;
    const findingCount = Array.isArray(findingIds) ? findingIds.length : undefined;
    return [
      channel !== undefined ? titleCaseEnum(channel) : undefined,
      findingCount !== undefined ? `${String(findingCount)} findings` : undefined,
    ]
      .filter(Boolean)
      .join(" · ");
  },
  DRAFT_UPDATED: (payload) => changedFieldNames(payload),
  DRAFT_EXPORTED: () => "—",
  CRM_PUSHED: (payload) =>
    [str(payload, "target"), str(payload, "status")]
      .filter(Boolean)
      .map((value) => titleCaseEnum(value ?? ""))
      .join(" · "),
  AI_CALL: (payload) => aiCallSubject(payload),
};

/** `FR-099`'s action filter: the closed [Audit actions]
 * (/architecture/sql-store.md#audit-actions) vocabulary. */
export const ALL_ACTIONS: AuditAction[] = Object.keys(SUBJECT_BUILDERS) as AuditAction[];

/** `FR-098`: the audit row's one-line subject. `action` is `API-60`'s closed vocabulary
 * ([Audit actions](/architecture/sql-store.md#audit-actions)), served as a plain string per
 * [`AuditEntry`](/architecture/interfaces.md#auditentry)'s contract. */
export function describeAuditEntry(entry: AuditEntry): string {
  return SUBJECT_BUILDERS[entry.action as AuditAction](entry.payload);
}
