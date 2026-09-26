import { CaretDownIcon, CaretRightIcon } from "@phosphor-icons/react";
import { Fragment, useState } from "react";
import { Link, useSearchParams } from "react-router";

import {
  useAuditLog,
  type AuditAction,
  type AuditEntry,
  type AuditEventKind,
} from "../../api/audit";
import { useUsers } from "../../api/authenticationAndUsers";
import { Button } from "../../components/Button";
import { Input, Select } from "../../components/controls";
import { Skeleton } from "../../components/Skeleton";
import { enumLabel, formatAbsolute } from "../../shell/format";
import { PageHeader } from "../../shell/PageHeader";
import { DataView } from "../../shell/states/DataView";
import { ALL_ACTIONS, CHANGE_KINDS, describeAuditEntry } from "./audit-labels";

const COLUMNS = ["When", "Who", "Action", "Subject"];
const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";

/** `FR-153`'s segmented control: All, AI calls or Changes (every other kind). */
type KindTab = "ALL" | "AI_CALL" | "CHANGES";

const KIND_TABS: { value: KindTab; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "AI_CALL", label: "AI calls" },
  { value: "CHANGES", label: "Changes" },
];

function kindTabOf(value: string | null): KindTab {
  return value === "AI_CALL" || value === "CHANGES" ? value : "ALL";
}

function kindsOfTab(tab: KindTab): AuditEventKind[] {
  if (tab === "AI_CALL") {
    return ["AI_CALL"];
  }
  return tab === "CHANGES" ? CHANGE_KINDS : [];
}

function actionOf(value: string | null): AuditAction | undefined {
  return ALL_ACTIONS.find((action) => action === value);
}

function SkeletonRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {[0, 1, 2, 3, 4].map((row) => (
        <Skeleton key={row} className="h-12 w-full" />
      ))}
    </div>
  );
}

/** S-AUD-02: Audit log, `/audit`, Admin only. WF-23. Renders `API-60` as it comes. */
export function AuditLogScreen() {
  const [params, setParams] = useSearchParams();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const users = useUsers();

  const kindTab = kindTabOf(params.get("kind"));
  const action = actionOf(params.get("action"));
  const actorId = params.get("actor_id") ?? "";
  const entityId = params.get("entity_id") ?? "";
  const runId = params.get("run_id") ?? "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const pageNumber = Number(params.get("page"));
  const page = Number.isInteger(pageNumber) && pageNumber >= 1 ? pageNumber : 1;

  const audit = useAuditLog({
    kinds: kindsOfTab(kindTab),
    action,
    actor_id: actorId,
    entity_id: entityId,
    run_id: runId,
    from,
    to,
    page,
  });

  /** FR-014: every filter and the page live in the URL; a change of filter returns to page one. */
  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [name, value] of Object.entries(patch)) {
      if (value === "") {
        next.delete(name);
      } else {
        next.set(name, value);
      }
    }
    if (!("page" in patch)) {
      next.delete("page");
    }
    setParams(next);
  };

  const data = audit.data;
  const pageCount = data === undefined ? 1 : Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <>
      <PageHeader
        title="Audit log"
        lead="Every configuration change, exception, piece of feedback, run and AI call, append-only."
      />
      <div className="flex flex-wrap items-end gap-3">
        <div role="group" aria-label="Kind" className="flex gap-1">
          {KIND_TABS.map((tab) => (
            <Button
              key={tab.value}
              size="small"
              variant={kindTab === tab.value ? "primary" : "secondary"}
              aria-pressed={kindTab === tab.value}
              onClick={() => {
                update({ kind: tab.value === "ALL" ? "" : tab.value });
              }}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        <label className={LABEL}>
          Action
          <Select
            value={action ?? ""}
            onChange={(event) => {
              update({ action: event.target.value });
            }}
          >
            <option value="">All actions</option>
            {ALL_ACTIONS.map((value) => (
              <option key={value} value={value}>
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
        <label className={LABEL}>
          User
          <Select
            value={actorId}
            onChange={(event) => {
              update({ actor_id: event.target.value });
            }}
          >
            <option value="">All users</option>
            {(users.data ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.display_name}
              </option>
            ))}
          </Select>
        </label>
        <label className={LABEL} htmlFor="audit-run">
          Run
          <Input
            id="audit-run"
            placeholder="Run id"
            value={runId}
            onChange={(event) => {
              update({ run_id: event.target.value });
            }}
          />
        </label>
        <label className={LABEL} htmlFor="audit-entity">
          Entity
          <Input
            id="audit-entity"
            placeholder="Entity id"
            value={entityId}
            onChange={(event) => {
              update({ entity_id: event.target.value });
            }}
          />
        </label>
        <label className={LABEL} htmlFor="audit-from">
          From
          <Input
            id="audit-from"
            type="date"
            value={from}
            onChange={(event) => {
              update({ from: event.target.value });
            }}
          />
        </label>
        <label className={LABEL} htmlFor="audit-to">
          To
          <Input
            id="audit-to"
            type="date"
            value={to}
            onChange={(event) => {
              update({ to: event.target.value });
            }}
          />
        </label>
      </div>
      <DataView
        query={audit}
        isEmpty={(result) => result.items.length === 0}
        skeleton={<SkeletonRows />}
        empty={{
          message: "No audit entries match these filters.",
          action: (
            <Button
              variant="secondary"
              onClick={() => {
                setParams(new URLSearchParams());
              }}
            >
              Clear filters
            </Button>
          ),
        }}
      >
        {(result) => (
          <div className="overflow-hidden rounded-card border border-border bg-surface">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  {COLUMNS.map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.items.map((entry) => (
                  <AuditRow
                    key={entry.id}
                    entry={entry}
                    expanded={expandedId === entry.id}
                    onToggle={() => {
                      setExpandedId((current) => (current === entry.id ? null : entry.id));
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataView>
      {data !== undefined && data.total > data.page_size && (
        <div className="flex items-center justify-between text-text-secondary">
          <span>{`Page ${String(page)} of ${String(pageCount)} · ${String(data.total)} entries`}</span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="small"
              disabled={page <= 1}
              onClick={() => {
                update({ page: String(page - 1) });
              }}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="small"
              disabled={page >= pageCount}
              onClick={() => {
                update({ page: String(page + 1) });
              }}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  );
}

function AuditRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: AuditEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <Fragment>
      <tr className="border-b border-border last:border-b-0">
        <td className="px-4 py-3">
          <button
            type="button"
            className="flex items-center gap-1.5 text-left hover:text-accent"
            aria-expanded={expanded}
            onClick={onToggle}
          >
            {expanded ? (
              <CaretDownIcon size={14} aria-hidden />
            ) : (
              <CaretRightIcon size={14} aria-hidden />
            )}
            {formatAbsolute(entry.occurred_at, timeZone)}
          </button>
        </td>
        <td className="px-4 py-3">{entry.actor_name ?? "System"}</td>
        <td className="px-4 py-3">{enumLabel(entry.action)}</td>
        <td className="px-4 py-3">{describeAuditEntry(entry)}</td>
      </tr>
      {expanded && (
        <tr className="border-b border-border last:border-b-0">
          <td colSpan={COLUMNS.length} className="px-4 py-3">
            <div className="flex flex-col gap-2 rounded-control bg-page p-3">
              {entry.run_id !== null && (
                <p className="m-0">
                  Run{" "}
                  <Link to="/runs" className="text-accent underline">
                    {entry.run_id}
                  </Link>
                </p>
              )}
              <pre className="m-0 overflow-x-auto whitespace-pre-wrap text-hint text-text-secondary">
                {JSON.stringify(entry.payload, null, 2)}
              </pre>
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}
