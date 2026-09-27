import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import {
  useEvaluationResult,
  useEvaluationResults,
  useImpact,
  useInvalidateEvaluationResults,
  useRequestQualityCheck,
  type EvaluationResult,
  type EvaluationResultSummary,
} from "../../../api/evaluation";
import { isRunFinal, useLatestEvaluationRun, useRun, type Run } from "../../../api/runs";
import { useServices } from "../../../api/servicesAndQuestions";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { Skeleton } from "../../../components/Skeleton";
import { enumLabel, formatAbsolute } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { DataView } from "../../../shell/states/DataView";
import { parseMetrics, type CalibrationBin, type Metrics, type Mistake } from "./metrics";

function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(0)}%`;
}

function runningStageSuffix(run: Run | undefined): string {
  if (run === undefined || run.stage === null) {
    return "";
  }
  return ` · ${enumLabel(run.stage)}`;
}

/** S-EVL-05: Quality report, `/quality`, Admin only. WF-18. */
export function QualityReportScreen() {
  const [params] = useSearchParams();
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);
  const latestEvaluationRun = useLatestEvaluationRun();
  const requestQualityCheck = useRequestQualityCheck();
  const invalidateEvaluation = useInvalidateEvaluationResults();
  const results = useEvaluationResults();

  const runningOnLoad = latestEvaluationRun.data?.items[0];
  const activeRunId =
    requestedRunId ??
    (runningOnLoad !== undefined && !isRunFinal(runningOnLoad) ? runningOnLoad.id : null);
  const activeRun = useRun(activeRunId ?? undefined);
  const isRunning = activeRun.data !== undefined && !isRunFinal(activeRun.data);
  const invalidatedForRunRef = useRef<string | null>(null);

  useEffect(() => {
    const data = activeRun.data;
    if (data !== undefined && isRunFinal(data) && invalidatedForRunRef.current !== data.id) {
      invalidatedForRunRef.current = data.id;
      void invalidateEvaluation();
    }
  }, [activeRun.data, invalidateEvaluation]);

  async function handleRunQualityCheck() {
    const run = await requestQualityCheck.mutateAsync();
    setRequestedRunId(run.id);
  }

  const openedRunId = params.get("run") ?? results.data?.[0]?.run_id;

  return (
    <>
      <PageHeader
        title="Quality report"
        lead="How well the classifier and the escalation band predict a person's label, on the labelled set."
        action={
          <Button
            variant="primary"
            disabled={isRunning}
            onClick={() => void handleRunQualityCheck()}
          >
            {isRunning ? `Running${runningStageSuffix(activeRun.data)}…` : "Run quality check"}
          </Button>
        }
      />
      {activeRun.data?.status === "FAILED" && (
        <Callout kind="error" lead="The quality check failed.">
          {activeRun.data.errors.map((error) => error.message).join(" ")}
        </Callout>
      )}
      <LatestResult runId={openedRunId} />
      <ImpactPanel />
    </>
  );
}

function LatestResult({ runId }: { runId: string | undefined }) {
  const result = useEvaluationResult(runId);
  const history = useEvaluationResults();

  return (
    <DataView
      query={result}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-96 w-full" />}
      empty={{ message: "No quality check has run yet.", action: null }}
    >
      {(data) => <ResultDetail result={data} history={history.data ?? []} />}
    </DataView>
  );
}

function ResultDetail({
  result,
  history,
}: {
  result: EvaluationResult;
  history: EvaluationResultSummary[];
}) {
  const metrics = parseMetrics(result.metrics);
  return (
    <div className="flex flex-col gap-6">
      <Callout kind={result.passed ? "accent" : "caution"}>
        This quality check {result.passed ? "passes" : "does not pass"} the release gate.
      </Callout>
      <GateSummary result={result} metrics={metrics} />
      <PerQuestionTable metrics={metrics} />
      <PerSourceTypeTable metrics={metrics} />
      <MissedEvidence metrics={metrics} />
      <CalibrationChart bins={metrics.calibration} />
      <MistakesList mistakes={metrics.errors} />
      <LeadVerdictBars leadVerdicts={metrics.lead_verdicts} />
      <HistoryList history={history} activeRunId={result.run_id} />
    </div>
  );
}

const METRIC_MEANINGS: Record<string, string> = {
  min_precision: "The release-gate precision threshold.",
  min_items: "The fewest labelled items a quality check needs to count.",
  precision: "Of the pairs predicted positive, the share a person also labelled positive.",
  recall: "Of the pairs a person labelled positive, the share predicted positive.",
  strength_agreement:
    "Of the true positives, the share whose predicted strength matches the label.",
  escalation_rate: "The share of items the band sent to the LLM.",
  classifier_only_precision: "Precision if the classifier decided alone, with no escalation.",
  classifier_only_recall: "Recall if the classifier decided alone, with no escalation.",
};

function GateSummary({ result, metrics }: { result: EvaluationResult; metrics: Metrics }) {
  const rows: { label: string; value: string; meaning: string }[] = [
    {
      label: "Minimum precision",
      value: percent(result.min_precision),
      meaning: METRIC_MEANINGS["min_precision"] ?? "",
    },
    {
      label: "Minimum items",
      value: String(result.min_items),
      meaning: METRIC_MEANINGS["min_items"] ?? "",
    },
    {
      label: "Precision",
      value: percent(metrics.precision),
      meaning: METRIC_MEANINGS["precision"] ?? "",
    },
    { label: "Recall", value: percent(metrics.recall), meaning: METRIC_MEANINGS["recall"] ?? "" },
    {
      label: "Strength agreement",
      value: percent(metrics.strength_agreement),
      meaning: METRIC_MEANINGS["strength_agreement"] ?? "",
    },
    {
      label: "Escalation rate",
      value: `${percent(metrics.escalation_rate)} (target ${percent(result.escalation_rate_target)})`,
      meaning: METRIC_MEANINGS["escalation_rate"] ?? "",
    },
    {
      label: "Classifier",
      value: enumLabel(result.classifier),
      meaning: "The adapter this check evaluated.",
    },
    {
      label: "Classifier-only precision",
      value: percent(metrics.classifier_only.precision),
      meaning: METRIC_MEANINGS["classifier_only_precision"] ?? "",
    },
    {
      label: "Classifier-only recall",
      value: percent(metrics.classifier_only.recall),
      meaning: METRIC_MEANINGS["classifier_only_recall"] ?? "",
    },
    {
      label: "Escalation band",
      value: `${percent(result.escalation_lower)} – ${percent(result.escalation_upper)}`,
      meaning:
        "Below the lower bound is negative, above the upper is positive, between escalates to the LLM.",
    },
    {
      label: "Items",
      value: String(result.items),
      meaning: "Active labelled items this check evaluated.",
    },
  ];
  return (
    <dl className="m-0 grid grid-cols-2 gap-x-8 gap-y-3 md:grid-cols-3">
      {rows.map((row) => (
        <div key={row.label}>
          <dt className="font-medium text-text-secondary">{row.label}</dt>
          <dd className="m-0 text-title font-semibold">{row.value}</dd>
          <dd className="m-0 text-hint text-text-tertiary">{row.meaning}</dd>
        </div>
      ))}
    </dl>
  );
}

function PerQuestionTable({ metrics }: { metrics: Metrics }) {
  const services = useServices();
  const serviceName = (serviceId: string): string =>
    services.data?.find((service) => service.id === serviceId)?.name ?? "";
  const rows = Object.entries(metrics.per_question);
  return (
    <section>
      <h2 className="text-body font-semibold">Per question</h2>
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-border text-hint text-text-tertiary">
            <th scope="col" className="px-2 py-2">
              Question
            </th>
            <th scope="col" className="px-2 py-2">
              Service
            </th>
            <th scope="col" className="px-2 py-2">
              Items
            </th>
            <th scope="col" className="px-2 py-2">
              Precision
            </th>
            <th scope="col" className="px-2 py-2">
              Recall
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([questionId, row]) => {
            const low =
              row.precision !== null && row.precision < (metrics.classifier_only.precision ?? 0);
            return (
              <tr key={questionId} className="border-b border-border last:border-b-0">
                <td className="px-2 py-2">{row.key}</td>
                <td className="px-2 py-2">{serviceName(row.service_id)}</td>
                <td className="px-2 py-2">{row.items}</td>
                <td className="px-2 py-2">
                  {percent(row.precision)}
                  {low && <Chip tone="caution">Below the gate</Chip>}
                </td>
                <td className="px-2 py-2">{percent(row.recall)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function PerSourceTypeTable({ metrics }: { metrics: Metrics }) {
  const rows = Object.entries(metrics.per_source_type);
  return (
    <section>
      <h2 className="text-body font-semibold">Per source type</h2>
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-border text-hint text-text-tertiary">
            <th scope="col" className="px-2 py-2">
              Source type
            </th>
            <th scope="col" className="px-2 py-2">
              Items
            </th>
            <th scope="col" className="px-2 py-2">
              Precision
            </th>
            <th scope="col" className="px-2 py-2">
              Recall
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([sourceType, row]) => (
            <tr key={sourceType} className="border-b border-border last:border-b-0">
              <td className="px-2 py-2">{enumLabel(sourceType)}</td>
              <td className="px-2 py-2">{row.items}</td>
              <td className="px-2 py-2">{percent(row.precision)}</td>
              <td className="px-2 py-2">{percent(row.recall)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function MissedEvidence({ metrics }: { metrics: Metrics }) {
  return (
    <p className="m-0">
      Missed evidence: {metrics.missed_evidence.items} item(s) the current passage selection does
      not read, {percent(metrics.missed_evidence.positive_rate)} of them labelled positive.
    </p>
  );
}

function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const width = 320;
  const height = 120;
  const barWidth = bins.length === 0 ? 0 : width / bins.length;
  return (
    <section>
      <h2 className="text-body font-semibold">Calibration</h2>
      <p className="m-0 text-hint text-text-tertiary">
        Each bar is one bin of predicted probability; its height is the share of items in that bin a
        person labelled positive. A well-calibrated classifier's bars rise left to right.
      </p>
      <svg
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        role="img"
        aria-label="Calibration chart"
      >
        {bins.map((bin, index) => {
          const barHeight = (bin.positive_rate ?? 0) * height;
          return (
            <rect
              key={index}
              x={index * barWidth}
              y={height - barHeight}
              width={Math.max(barWidth - 2, 1)}
              height={barHeight}
              className="fill-accent"
            />
          );
        })}
      </svg>
    </section>
  );
}

function MistakesList({ mistakes }: { mistakes: Mistake[] }) {
  return (
    <section>
      <h2 className="text-body font-semibold">Mistakes</h2>
      {mistakes.length === 0 ? (
        <p className="m-0 text-text-secondary">No misclassified items.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {mistakes.map((mistake) => (
            <li key={mistake.item_id} className="rounded-control border border-border p-3">
              <p className="m-0">{mistake.passage_text}</p>
              <p className="m-0 text-hint text-text-tertiary">
                Expected {mistake.expected}, predicted {mistake.predicted}
                {mistake.question_key !== null && ` · ${mistake.question_key}`}
              </p>
              {mistake.document !== null && (
                <a
                  href={mistake.document.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent-ink underline"
                >
                  {mistake.document.title ?? mistake.document.url}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LeadVerdictBars({
  leadVerdicts,
}: {
  leadVerdicts: Record<string, { RELEVANT: number; NOT_RELEVANT: number }>;
}) {
  const bands = Object.entries(leadVerdicts);
  return (
    <section>
      <h2 className="text-body font-semibold">Lead verdicts by band</h2>
      {bands.length === 0 ? (
        <p className="m-0 text-text-secondary">No lead feedback yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {bands.map(([band, counts]) => (
            <div key={band} className="flex items-center gap-3">
              <span className="w-16">{enumLabel(band)}</span>
              <span className="text-positive">Relevant {counts.RELEVANT}</span>
              <span className="text-negative">Not relevant {counts.NOT_RELEVANT}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function HistoryList({
  history,
  activeRunId,
}: {
  history: EvaluationResultSummary[];
  activeRunId: string;
}) {
  const [, setParams] = useSearchParams();
  return (
    <section>
      <h2 className="text-body font-semibold">History</h2>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {history.map((entry) => (
          <li key={entry.run_id}>
            <button
              type="button"
              className="underline aria-[current=true]:font-semibold"
              aria-current={entry.run_id === activeRunId}
              onClick={() => {
                setParams({ run: entry.run_id });
              }}
            >
              {formatAbsolute(entry.created_at, Intl.DateTimeFormat().resolvedOptions().timeZone)} ·{" "}
              {enumLabel(entry.classifier)} · {entry.items} items ·{" "}
              {entry.passed ? "Passed" : "Failed"}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ImpactPanel() {
  const impact = useImpact();
  return (
    <DataView
      query={impact}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-40 w-full" />}
      empty={{ message: "No impact data yet.", action: null }}
    >
      {(data) => (
        <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6">
          <h2 className="text-body font-semibold">Impact</h2>
          <dl className="m-0 grid grid-cols-2 gap-x-8 gap-y-3 md:grid-cols-3">
            <div>
              <dt className="font-medium text-text-secondary">Accounts refreshed</dt>
              <dd className="m-0 text-title font-semibold">{data.accounts_refreshed}</dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Refreshes</dt>
              <dd className="m-0 text-title font-semibold">{data.refreshes}</dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Cost per refresh</dt>
              <dd className="m-0 text-title font-semibold">
                {data.cost_per_refresh_eur === null
                  ? "—"
                  : `€${data.cost_per_refresh_eur.toFixed(2)}`}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Minutes per refresh</dt>
              <dd className="m-0 text-title font-semibold">
                {data.minutes_per_refresh === null ? "—" : data.minutes_per_refresh.toFixed(1)}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Findings created</dt>
              <dd className="m-0 text-title font-semibold">{data.findings_created}</dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Precision</dt>
              <dd className="m-0 text-title font-semibold">{percent(data.precision)}</dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Labelled items</dt>
              <dd className="m-0 text-title font-semibold">{data.labelled_items ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">
                Manual minutes per account (assumption)
              </dt>
              <dd className="m-0 text-title font-semibold">{data.manual_minutes_per_account}</dd>
            </div>
            <div>
              <dt className="font-medium text-text-secondary">Manual hours replaced</dt>
              <dd className="m-0 text-title font-semibold">{data.manual_hours_replaced}</dd>
            </div>
          </dl>
          <p className="m-0 text-text-secondary">
            Researching one account by hand takes {data.manual_minutes_per_account} minutes;
            LeadRadar refreshed {data.accounts_refreshed} accounts
            {data.cost_per_refresh_eur !== null && ` at €${data.cost_per_refresh_eur.toFixed(2)}`}
            {data.minutes_per_refresh !== null &&
              ` and ${data.minutes_per_refresh.toFixed(1)} minutes`}{" "}
            each, finding {data.findings_created} signals
            {data.precision !== null &&
              data.labelled_items !== null &&
              `, at ${percent(data.precision)} precision on ${String(data.labelled_items)} labelled passages`}
            .
          </p>
        </section>
      )}
    </DataView>
  );
}
