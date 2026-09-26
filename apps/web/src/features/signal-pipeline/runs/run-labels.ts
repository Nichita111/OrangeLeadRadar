/**
 * Pure presentation rules for [Runs](/features/signal-pipeline.md#runs) (`FR-054` to `FR-056`): no
 * I/O, a run is only ever rendered from the [`Run`](/architecture/interfaces.md#run) contract.
 */
import type { PipelineRunKind, PipelineRunStage, Run } from "../../../api/runs";
import type { StepState, StepperStep } from "../../../components/motion/Stepper";

/** [Glossary](/requirements/glossary.md) terms and the [screen labels]
 * (/architecture/services/frontend.md#screen-labels) "Evaluation run" row; `RECLASSIFY` has
 * neither, so `FR-011`'s title-cased fallback names it. */
export const RUN_KIND_LABELS: Record<PipelineRunKind, string> = {
  ACCOUNT_REFRESH: "Account refresh",
  RECLASSIFY: "Reclassify",
  RESCORE: "Rescore",
  DISCOVERY: "Discovery",
  EVALUATION: "Quality check",
};

/** The stages each kind passes through, in order ([Run lifecycle]
 * (/architecture/services/worker.md#run-lifecycle)). */
export const RUN_KIND_STAGES: Record<PipelineRunKind, PipelineRunStage[]> = {
  ACCOUNT_REFRESH: ["FETCH", "PROCESS", "TRIAGE", "CLASSIFY", "EVIDENCE", "SCORE"],
  RECLASSIFY: ["TRIAGE", "CLASSIFY", "EVIDENCE", "SCORE"],
  RESCORE: ["SCORE"],
  DISCOVERY: ["FETCH", "TRIAGE", "SCORE"],
  EVALUATION: ["CLASSIFY"],
};

const STAGE_LABELS: Record<PipelineRunStage, string> = {
  FETCH: "Fetch",
  PROCESS: "Process",
  TRIAGE: "Triage",
  CLASSIFY: "Classify",
  EVIDENCE: "Evidence",
  SCORE: "Score",
};

/** The one-line, present-tense form of each stage while it is `current` (`FR-054`, `FR-058`). */
const STAGE_RUNNING_LABELS: Record<PipelineRunStage, string> = {
  FETCH: "Fetching sources",
  PROCESS: "Processing documents",
  TRIAGE: "Checking relevance",
  CLASSIFY: "Classifying passages",
  EVIDENCE: "Extracting evidence",
  SCORE: "Scoring",
};

/** `FR-055`: the run's stages with done, current and pending marks, in the [`Stepper`]
 * (../../../components/motion/Stepper.tsx) shape. */
export function runStageSteps(run: Run): StepperStep[] {
  const order = RUN_KIND_STAGES[run.kind];
  const currentIndex = run.stage === null ? -1 : order.indexOf(run.stage);
  const isFinished = !run.stage && run.finished_at !== null;
  return order.map((stage, index) => {
    let state: StepState = "pending";
    if (isFinished || (currentIndex >= 0 && index < currentIndex)) {
      state = "done";
    } else if (index === currentIndex) {
      state = "current";
    }
    return { key: stage, label: STAGE_LABELS[stage], state };
  });
}

/** [`pipeline_run`](/architecture/sql-store.md#pipeline_run) `progress` counters, each with the
 * plain word `FR-055` asks for; unlisted keys (none documented) are never invented. */
const PROGRESS_LABELS: { key: string; label: (n: number) => string }[] = [
  { key: "documents_fetched", label: (n) => `${String(n)} fetched` },
  { key: "documents_new", label: (n) => `${String(n)} new` },
  { key: "documents_kept", label: (n) => `${String(n)} kept` },
  { key: "passages", label: (n) => `${String(n)} passages` },
  { key: "pairs_escalated", label: (n) => `${String(n)} detailed checks` },
  { key: "findings_created", label: (n) => `${String(n)} signals` },
  { key: "candidates", label: (n) => `${String(n)} candidates` },
  { key: "items_evaluated", label: (n) => `${String(n)} checked` },
];

function progressBreakdown(run: Run): string[] {
  return PROGRESS_LABELS.filter(({ key }) => run.progress[key] !== undefined).map(
    ({ key, label }) => label(run.progress[key] ?? 0),
  );
}

/** `FR-056`: which plug-ins failed, and how many signals are waiting for the next refresh
 * (`pending_budget`). */
function partialReason(run: Run): string {
  const failedPlugins = Array.from(
    new Set(
      run.errors
        .map((error) => error.plugin_code)
        .filter((code): code is NonNullable<typeof code> => code !== null && code !== undefined),
    ),
  );
  const parts: string[] = failedPlugins.map((code) => `${code} failed`);
  const waiting = run.progress.pending_budget;
  if (waiting !== undefined && waiting > 0) {
    parts.push(`${String(waiting)} waiting`);
  }
  return parts.length > 0 ? parts.join(" · ") : "Partial";
}

/** `FR-054`: one line, in the [screen labels](/architecture/services/frontend.md#screen-labels),
 * never the stage's internal counters' raw names. */
export function describeRunProgress(run: Run): string {
  if (run.status === "PARTIAL") {
    return partialReason(run);
  }
  if (run.status === "FAILED") {
    return run.errors.at(-1)?.message ?? "Failed";
  }
  if (run.status === "CANCELLED") {
    return "Cancelled";
  }
  if (run.status === "QUEUED") {
    return "Queued";
  }
  if (run.status === "RUNNING") {
    if (run.stage === "CLASSIFY" && run.progress.passages !== undefined) {
      const classified = run.progress.pairs_classified ?? 0;
      return `Checking passages ${String(classified)}/${String(run.progress.passages)}`;
    }
    return run.stage !== null ? STAGE_RUNNING_LABELS[run.stage] : "Running";
  }
  const breakdown = progressBreakdown(run);
  return breakdown.length > 0 ? breakdown.join(" · ") : "Succeeded";
}

/** The subject column of `FR-054`: the account, service or question the run is about. */
export function runSubject(run: Run): string {
  return run.account?.name ?? run.service?.name ?? run.question?.key ?? "—";
}
