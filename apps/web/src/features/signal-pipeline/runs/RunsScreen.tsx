import { useSearchParams } from "react-router";

import type { Schemas } from "../../../api/contract";
import { isRunFinal, useCancelRun, useRun, useRuns, type Run } from "../../../api/runs";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip, type ChipTone } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { Select } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { useCurrentUser } from "../../../shell/CurrentUser";
import { enumLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";

type Kind = Schemas["PipelineRunKind"];
type Status = Schemas["PipelineRunStatus"];
type Stage = Schemas["PipelineRunStage"];

const KINDS: Kind[] = ["ACCOUNT_REFRESH", "RECLASSIFY", "RESCORE", "DISCOVERY", "EVALUATION"];
const STATUSES: Status[] = ["QUEUED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"];

/** The stages each kind of run goes through, in order ([worker Run lifecycle]). */
const STAGES: Record<Kind, Stage[]> = {
  ACCOUNT_REFRESH: ["FETCH", "PROCESS", "TRIAGE", "CLASSIFY", "EVIDENCE", "SCORE"],
  RECLASSIFY: ["TRIAGE", "CLASSIFY", "EVIDENCE", "SCORE"],
  RESCORE: ["SCORE"],
  DISCOVERY: ["FETCH", "TRIAGE", "SCORE"],
  EVALUATION: ["CLASSIFY"],
};

/** Runs an Admin alone may cancel (`FR-057`). */
const ADMIN_CANCEL: Kind[] = ["RECLASSIFY", "RESCORE", "EVALUATION"];

const STATUS_TONE: Record<Status, ChipTone> = {
  QUEUED: "neutral",
  RUNNING: "cool",
  SUCCEEDED: "positive",
  PARTIAL: "caution",
  FAILED: "negative",
  CANCELLED: "neutral",
};

function subject(run: Run): string {
  return run.account?.name ?? run.question?.key ?? run.service?.name ?? "All accounts";
}

function duration(run: Run): string {
  if (run.started_at === null) {
    return "—";
  }
  const end = run.finished_at === null ? Date.now() : Date.parse(run.finished_at);
  const seconds = Math.max(0, Math.round((end - Date.parse(run.started_at)) / 1000));
  return seconds < 60
    ? `${String(seconds)} s`
    : `${String(Math.floor(seconds / 60))} min ${String(seconds % 60)} s`;
}

/** The counters a one-line summary shows, in this order (`FR-054`). */
const SUMMARY_COUNTERS = [
  "documents_fetched",
  "documents_new",
  "findings_created",
  "scored",
  "organisations_found",
];

/** One line of the run's main counters in plain words (`FR-054`). */
function progressLine(run: Run, counters: readonly string[] = SUMMARY_COUNTERS): string {
  const parts = counters.flatMap((key) => {
    const value = run.progress[key];
    return typeof value === "number" ? [`${String(value)} ${key.replaceAll("_", " ")}`] : [];
  });
  return parts.length === 0 ? "—" : parts.join(" · ");
}

/** Every counter of the run, for its detail panel (`FR-055`). */
function allCounters(run: Run): string {
  return progressLine(run, Object.keys(run.progress));
}

/** `FR-056`: why a `PARTIAL` run is partial, in one line. */
function partialReason(run: Run): string | null {
  if (run.status !== "PARTIAL") {
    return null;
  }
  const plugins = [
    ...new Set(run.errors.flatMap((error) => (error.plugin_code ? [error.plugin_code] : []))),
  ];
  const stages = [
    ...new Set(run.errors.filter((error) => !error.plugin_code).map((error) => error.stage)),
  ];
  const parts = [
    plugins.length > 0 ? `${plugins.map(enumLabel).join(", ")} could not be read` : null,
    stages.length > 0 ? `the ${stages.map(enumLabel).join(", ")} stage had errors` : null,
  ].filter((part) => part !== null);
  return `Partly done: ${parts.join("; ")}. The rest is kept and the next refresh retries.`;
}

/** S-PIP-06: Runs, `/runs`, any signed-in user. FR-054 to FR-058. */
export function RunsScreen() {
  const [params, setParams] = useSearchParams();
  const kind = KINDS.find((value) => value === params.get("kind"));
  const status = STATUSES.find((value) => value === params.get("status"));
  const selected = params.get("run") ?? undefined;
  const runs = useRuns({ kind, status, accountId: params.get("account") ?? undefined });

  const setParam = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(params);
    if (value === undefined || value === "") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setParams(next);
  };

  return (
    <>
      <PageHeader
        title="Runs"
        lead="Every refresh, reclassification, rescore, discovery and quality check, newest first."
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-hint text-text-tertiary">
          Kind
          <Select
            value={kind ?? ""}
            onChange={(event) => {
              setParam("kind", event.target.value);
            }}
          >
            <option value="">All kinds</option>
            {KINDS.map((value) => (
              <option key={value} value={value}>
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
        <label className="flex flex-col gap-1 text-hint text-text-tertiary">
          Status
          <Select
            value={status ?? ""}
            onChange={(event) => {
              setParam("status", event.target.value);
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_360px] items-start gap-6">
        <div className="min-w-0 overflow-x-auto">
          <DataView
            query={runs}
            isEmpty={(page) => page.items.length === 0}
            skeleton={<Skeleton className="h-64 w-full" />}
            empty={{ message: "No run matches these filters yet.", action: null }}
          >
            {(page) => (
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-border text-hint text-text-tertiary">
                    {[
                      "Kind",
                      "Subject",
                      "Trigger",
                      "By",
                      "Started",
                      "Duration",
                      "Status",
                      "Progress",
                    ].map((heading) => (
                      <th key={heading} scope="col" className="px-3 py-2 font-medium">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((run) => (
                    <tr
                      key={run.id}
                      aria-selected={run.id === selected}
                      className={`cursor-pointer border-b border-border last:border-b-0 hover:bg-surface-raised ${
                        run.id === selected ? "bg-surface-raised" : ""
                      }`}
                      onClick={() => {
                        setParam("run", run.id);
                      }}
                    >
                      <td className="px-3 py-2">{enumLabel(run.kind)}</td>
                      <td className="px-3 py-2">{subject(run)}</td>
                      <td className="px-3 py-2 text-text-secondary">{enumLabel(run.trigger)}</td>
                      <td className="px-3 py-2 text-text-secondary">
                        {run.requested_by_name ?? "Scheduler"}
                      </td>
                      <td className="px-3 py-2 text-text-secondary">
                        {run.started_at === null ? "Not yet" : <RelativeTime at={run.started_at} />}
                      </td>
                      <td className="num px-3 py-2">{duration(run)}</td>
                      <td className="px-3 py-2">
                        <Chip tone={STATUS_TONE[run.status]}>{enumLabel(run.status)}</Chip>
                      </td>
                      <td className="px-3 py-2 text-hint text-text-secondary">
                        {progressLine(run)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DataView>
        </div>
        {selected === undefined ? (
          <p className="m-0 text-text-secondary">Select a run to see its stages and errors.</p>
        ) : (
          <RunDetail runId={selected} />
        )}
      </div>
    </>
  );
}

function RunDetail({ runId }: { runId: string }) {
  const run = useRun(runId);
  const cancel = useCancelRun();
  const isAdmin = useCurrentUser().role === "ADMIN";

  if (run.data === undefined) {
    return run.error === null ? (
      <Skeleton className="h-64 w-full" />
    ) : (
      <Callout kind="error">{run.error.message}</Callout>
    );
  }
  const data = run.data;
  const stages = STAGES[data.kind];
  const current = data.stage === null ? -1 : stages.indexOf(data.stage);
  const final = isRunFinal(data);
  const canCancel = !final && (isAdmin || !ADMIN_CANCEL.includes(data.kind));
  const reason = partialReason(data);

  return (
    <section
      aria-label="Selected run"
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4"
    >
      <div className="flex items-center justify-between">
        <h2 className="m-0 text-section font-semibold">
          {enumLabel(data.kind)} · {subject(data)}
        </h2>
        <Chip tone={STATUS_TONE[data.status]}>{enumLabel(data.status)}</Chip>
      </div>
      <ol className="m-0 flex list-none flex-col gap-1 p-0">
        {stages.map((stage, index) => {
          const done =
            data.status === "SUCCEEDED" ||
            data.status === "PARTIAL" ||
            index < current ||
            (final && index <= current);
          const mark = done ? "✓" : index === current && !final ? "●" : "○";
          return (
            <li key={stage} className="flex gap-2">
              <span aria-hidden className="w-4 text-center">
                {mark}
              </span>
              <span className={index === current && !final ? "font-semibold" : ""}>
                {enumLabel(stage)}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="m-0 text-text-secondary">{allCounters(data)}</p>
      {reason !== null && <Callout kind="caution">{reason}</Callout>}
      {data.errors.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {data.errors.map((error, index) => (
            <li key={index} className="text-hint">
              <span className="font-medium">
                {enumLabel(error.stage)}
                {error.plugin_code ? ` · ${enumLabel(error.plugin_code)}` : ""}
              </span>
              <span className="block break-all text-text-tertiary" title={error.message}>
                {enumLabel(error.code)}:{" "}
                {error.message.length > 140 ? `${error.message.slice(0, 140)}…` : error.message}
              </span>
            </li>
          ))}
        </ul>
      )}
      {isAdmin && (
        <p className="m-0 text-hint text-text-tertiary">AI cost €{data.ai_cost_eur.toFixed(2)}</p>
      )}
      {canCancel && (
        <ConfirmDialog
          trigger={<Button variant="secondary">Cancel run</Button>}
          title="Cancel this run?"
          description="Steps already running finish first; nothing further is started."
          confirmLabel="Cancel run"
          onConfirm={() => {
            cancel.mutate(data.id);
          }}
        />
      )}
      {cancel.error !== null && <Callout kind="error">{cancel.error.message}</Callout>}
    </section>
  );
}
