/**
 * [Runs](/features/signal-pipeline.md#runs). Route `/runs`, any signed-in user; cost and
 * technical counters are Admin only. WF-10.
 */
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useRuntimeConfig } from "../../../shell/config-context";
import {
  isRunLive,
  useCancelRun,
  useRun,
  useRuns,
  type PipelineRunKind,
  type PipelineRunStatus,
  type Run,
} from "../../../api/runs";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip, type ChipTone } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/Dialog";
import { Select } from "../../../components/Select";
import { EmptyState, ErrorState, SkeletonRows, UnavailableState } from "../../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../../components/Table";
import { ShimmerLabel } from "../../../components/motion/ShimmerLabel";
import { Stepper } from "../../../components/motion/Stepper";
import { useCurrentUser } from "../../../shell/current-user-context";
import {
  formatAbsoluteDateTime,
  formatDuration,
  formatRelativeDate,
  titleCaseEnum,
} from "../../../shell/formatting";
import { describeRunProgress, runStageSteps, runSubject, RUN_KIND_LABELS } from "./run-labels";

const COLUMN_COUNT = 7;

/** `API-36`: Admin only for these three kinds ([Runs and source plug-ins]
 * (/architecture/interfaces.md#runs-and-source-plug-ins-contracts)). */
const ADMIN_ONLY_CANCEL_KINDS: PipelineRunKind[] = ["RECLASSIFY", "RESCORE", "EVALUATION"];

const STATUS_TONE: Record<PipelineRunStatus, ChipTone> = {
  QUEUED: "neutral",
  RUNNING: "accent",
  SUCCEEDED: "positive",
  PARTIAL: "caution",
  FAILED: "negative",
  CANCELLED: "cool",
};

function StatusChip({ status }: { status: PipelineRunStatus }) {
  const label = titleCaseEnum(status);
  return (
    <Chip tone={STATUS_TONE[status]}>
      {status === "RUNNING" ? <ShimmerLabel>{label}</ShimmerLabel> : label}
    </Chip>
  );
}

export function RunsScreen() {
  const currentUser = useCurrentUser();
  const config = useRuntimeConfig();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Run | null>(null);

  const kind = searchParams.get("kind") as PipelineRunKind | null;
  const status = searchParams.get("status") as PipelineRunStatus | null;

  const {
    data: page,
    isLoading,
    isError,
    error,
    refetch,
  } = useRuns(
    { ...(kind ? { kind } : {}), ...(status ? { status } : {}) },
    config.RUN_POLL_INTERVAL_MS,
  );
  const selected = useRun(selectedRunId ?? undefined, config.RUN_POLL_INTERVAL_MS);
  const cancelRun = useCancelRun();

  const setFilter = (key: "kind" | "status", value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value === "") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next);
  };

  const canCancel = (run: Run): boolean =>
    isRunLive(run.status) &&
    (!ADMIN_ONLY_CANCEL_KINDS.includes(run.kind) || currentUser.role === "ADMIN");

  const handleConfirmCancel = () => {
    if (cancelTarget === null) {
      return;
    }
    cancelRun.mutate(cancelTarget.id, {
      onSuccess: () => {
        setCancelTarget(null);
      },
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[24px] font-semibold text-text">Runs</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Follow every refresh, rescore and quality check, live, and cancel one that is still under
          way.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Select
          id="runs-kind"
          label="Kind"
          value={kind ?? ""}
          onValueChange={(value) => {
            setFilter("kind", value);
          }}
          options={[
            { value: "", label: "All kinds" },
            ...Object.entries(RUN_KIND_LABELS).map(([value, label]) => ({ value, label })),
          ]}
        />
        <Select
          id="runs-status"
          label="Status"
          value={status ?? ""}
          onValueChange={(value) => {
            setFilter("status", value);
          }}
          options={[
            { value: "", label: "All statuses" },
            ...(["QUEUED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"] as const).map(
              (value) => ({ value, label: titleCaseEnum(value) }),
            ),
          ]}
        />
      </div>

      <Table caption="Runs">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Kind</TableHeaderCell>
            <TableHeaderCell>Subject</TableHeaderCell>
            <TableHeaderCell>Requester</TableHeaderCell>
            <TableHeaderCell>Started</TableHeaderCell>
            <TableHeaderCell>Duration</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Progress</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading && <SkeletonRows rows={3} columns={COLUMN_COUNT} />}
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
          {!isLoading && !isError && page !== undefined && page.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <EmptyState
                  message="No runs match these filters yet. A refresh, rescore or quality check will appear here once it starts."
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
            page?.items.map((run) => (
              <TableRow key={run.id}>
                <TableCell>
                  <button
                    type="button"
                    className="text-left text-accent hover:underline"
                    onClick={() => {
                      setSelectedRunId(run.id);
                    }}
                  >
                    {RUN_KIND_LABELS[run.kind]}
                  </button>
                </TableCell>
                <TableCell>{runSubject(run)}</TableCell>
                <TableCell>{run.requested_by_name ?? "Scheduler"}</TableCell>
                <TableCell>
                  <span
                    title={
                      run.started_at !== null ? formatAbsoluteDateTime(run.started_at) : undefined
                    }
                  >
                    {run.started_at !== null ? formatRelativeDate(run.started_at) : "Queued"}
                  </span>
                </TableCell>
                <TableCell>{formatDuration(run.started_at, run.finished_at)}</TableCell>
                <TableCell>
                  <StatusChip status={run.status} />
                </TableCell>
                <TableCell>{describeRunProgress(run)}</TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>

      {selectedRunId !== null && selected.data !== undefined && (
        <div className="flex flex-col gap-4 rounded-card border border-border bg-surface p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[15px] font-semibold text-text">
                {runSubject(selected.data)} · {RUN_KIND_LABELS[selected.data.kind]}
                {selected.data.requested_by_name !== null &&
                  ` · by ${selected.data.requested_by_name}`}
              </h2>
              <p className="mt-1 text-sm text-text-secondary">
                {describeRunProgress(selected.data)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {currentUser.role === "ADMIN" && (
                <span className="font-mono text-sm text-text-tertiary">
                  AI cost €{selected.data.ai_cost_eur.toFixed(2)}
                </span>
              )}
              {canCancel(selected.data) && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setCancelTarget(selected.data);
                  }}
                >
                  Cancel
                </Button>
              )}
            </div>
          </div>

          <Stepper steps={runStageSteps(selected.data)} />

          {selected.data.errors.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {selected.data.errors.map((runError, index) => (
                <Callout key={index} kind="error">
                  <strong>{titleCaseEnum(runError.stage)}</strong>
                  {runError.plugin_code !== null && runError.plugin_code !== undefined
                    ? ` · ${runError.plugin_code}`
                    : ""}{" "}
                  — {runError.message}
                </Callout>
              ))}
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={cancelTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCancelTarget(null);
          }
        }}
        title="Cancel run"
        description="Running steps finish their current step before the run stops; work already done is kept."
        confirmLabel="Cancel run"
        onConfirm={handleConfirmCancel}
        confirmPending={cancelRun.isPending}
      />
    </div>
  );
}
