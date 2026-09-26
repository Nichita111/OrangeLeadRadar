/**
 * [Audit log](/features/audit-trail.md#audit-log). Route `/audit`, Admin only. WF-23.
 */
import { Fragment, useState } from "react";
import { CaretDownIcon, CaretRightIcon } from "@phosphor-icons/react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  useAuditLog,
  type AuditAction,
  type AuditEntry,
  type AuditEventKind,
} from "../../api/audit";
import { useUsers } from "../../api/users";
import { Button } from "../../components/Button";
import { Input } from "../../components/Input";
import { Select } from "../../components/Select";
import { EmptyState, ErrorState, SkeletonRows, UnavailableState } from "../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../components/Table";
import { formatAbsoluteDateTime, titleCaseEnum } from "../../shell/formatting";
import { ALL_ACTIONS, CHANGE_KINDS, describeAuditEntry } from "./audit-labels";

const COLUMN_COUNT = 4;

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

function kindsOfTab(tab: KindTab): AuditEventKind[] | undefined {
  if (tab === "AI_CALL") {
    return ["AI_CALL"];
  }
  if (tab === "CHANGES") {
    return CHANGE_KINDS;
  }
  return undefined;
}

export function AuditLogScreen() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const kindTab = kindTabOf(searchParams.get("kind"));
  const action = searchParams.get("action") ?? "";
  const actorId = searchParams.get("actor_id") ?? "";
  const entityId = searchParams.get("entity_id") ?? "";
  const runId = searchParams.get("run_id") ?? "";
  const from = searchParams.get("from") ?? "";
  const to = searchParams.get("to") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  const { data: users } = useUsers();
  const kinds = kindsOfTab(kindTab);
  const {
    data: entryPage,
    isLoading,
    isError,
    error,
    refetch,
  } = useAuditLog({
    ...(kinds !== undefined ? { kind: kinds } : {}),
    ...(action.length > 0 ? { action: action as AuditAction } : {}),
    ...(actorId.length > 0 ? { actor_id: actorId } : {}),
    ...(entityId.length > 0 ? { entity_id: entityId } : {}),
    ...(runId.length > 0 ? { run_id: runId } : {}),
    ...(from.length > 0 ? { from } : {}),
    ...(to.length > 0 ? { to } : {}),
    page,
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value === "") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    next.delete("page");
    setSearchParams(next);
  };

  const setPage = (value: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(value));
    setSearchParams(next);
  };

  const lastPage =
    entryPage !== undefined ? Math.max(1, Math.ceil(entryPage.total / entryPage.page_size)) : 1;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[24px] font-semibold text-text">Audit log</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Every configuration change, exception, piece of feedback, run and AI call, append-only.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-text">Kind</span>
          <div className="flex overflow-hidden rounded-control border border-border">
            {KIND_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                aria-pressed={kindTab === tab.value}
                onClick={() => {
                  setFilter("kind", tab.value === "ALL" ? "" : tab.value);
                }}
                className={`px-3 text-sm font-medium transition-colors ${
                  kindTab === tab.value
                    ? "bg-accent text-on-accent"
                    : "bg-surface text-text hover:bg-page"
                }`}
                style={{ height: "var(--ctl-input)" }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <Select
          id="audit-action"
          label="Action"
          value={action}
          onValueChange={(value) => {
            setFilter("action", value);
          }}
          options={[
            { value: "", label: "All actions" },
            ...ALL_ACTIONS.map((value) => ({ value, label: titleCaseEnum(value) })),
          ]}
        />
        <Select
          id="audit-user"
          label="User"
          value={actorId}
          onValueChange={(value) => {
            setFilter("actor_id", value);
          }}
          options={[
            { value: "", label: "All users" },
            ...(users ?? []).map((user) => ({ value: user.id, label: user.display_name })),
          ]}
        />
        <Input
          id="audit-run"
          label="Run"
          placeholder="Run id"
          value={runId}
          onChange={(event) => {
            setFilter("run_id", event.target.value);
          }}
        />
        <Input
          id="audit-entity"
          label="Entity"
          placeholder="Entity id"
          value={entityId}
          onChange={(event) => {
            setFilter("entity_id", event.target.value);
          }}
        />
        <Input
          id="audit-from"
          label="From"
          type="date"
          value={from}
          onChange={(event) => {
            setFilter("from", event.target.value);
          }}
        />
        <Input
          id="audit-to"
          label="To"
          type="date"
          value={to}
          onChange={(event) => {
            setFilter("to", event.target.value);
          }}
        />
      </div>

      <Table caption="Audit log">
        <TableHead>
          <TableRow>
            <TableHeaderCell>When</TableHeaderCell>
            <TableHeaderCell>Who</TableHeaderCell>
            <TableHeaderCell>Action</TableHeaderCell>
            <TableHeaderCell>Subject</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading && <SkeletonRows rows={6} columns={COLUMN_COUNT} />}
          {!isLoading && isError && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                {error instanceof ApiError && (error.status === 503 || error.status === 429) ? (
                  <UnavailableState
                    dependency={
                      typeof error.details?.dependency === "string"
                        ? error.details.dependency
                        : "The database"
                    }
                    stillWorks={[]}
                  />
                ) : (
                  <ErrorState
                    message={error instanceof ApiError ? error.message : "Something went wrong."}
                    onRetry={() => void refetch()}
                  />
                )}
              </TableCell>
            </TableRow>
          )}
          {!isLoading && !isError && entryPage !== undefined && entryPage.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <EmptyState
                  message="No audit entries match these filters."
                  actionLabel="Clear filters"
                  onAction={() => {
                    setSearchParams(new URLSearchParams());
                  }}
                />
              </TableCell>
            </TableRow>
          )}
          {!isLoading &&
            !isError &&
            entryPage?.items.map((entry) => (
              <AuditRow
                key={entry.id}
                entry={entry}
                expanded={expandedId === entry.id}
                onToggle={() => {
                  setExpandedId((current) => (current === entry.id ? null : entry.id));
                }}
              />
            ))}
        </TableBody>
      </Table>

      {entryPage !== undefined && entryPage.total > entryPage.page_size && (
        <div className="flex items-center justify-between text-sm text-text-secondary">
          <span>
            Page {String(page)} of {String(lastPage)} · {String(entryPage.total)} entries
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="small"
              disabled={page <= 1}
              onClick={() => {
                setPage(page - 1);
              }}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="small"
              disabled={page >= lastPage}
              onClick={() => {
                setPage(page + 1);
              }}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
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
  return (
    <Fragment>
      <TableRow>
        <TableCell>
          <button
            type="button"
            className="flex items-center gap-1.5 text-left text-text hover:text-accent"
            aria-expanded={expanded}
            onClick={onToggle}
          >
            {expanded ? (
              <CaretDownIcon size={14} aria-hidden="true" />
            ) : (
              <CaretRightIcon size={14} aria-hidden="true" />
            )}
            {formatAbsoluteDateTime(entry.occurred_at)}
          </button>
        </TableCell>
        <TableCell>{entry.actor_name ?? "system"}</TableCell>
        <TableCell>{titleCaseEnum(entry.action)}</TableCell>
        <TableCell>{describeAuditEntry(entry)}</TableCell>
      </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={COLUMN_COUNT}>
            <div className="flex flex-col gap-2 rounded-control bg-page p-3">
              {entry.run_id !== null && (
                <p className="text-sm text-text">
                  Run{" "}
                  <Link to="/runs" className="text-accent underline">
                    {entry.run_id}
                  </Link>
                </p>
              )}
              <pre className="overflow-x-auto whitespace-pre-wrap text-[12.5px] text-text-secondary">
                {JSON.stringify(entry.payload, null, 2)}
              </pre>
            </div>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  );
}
