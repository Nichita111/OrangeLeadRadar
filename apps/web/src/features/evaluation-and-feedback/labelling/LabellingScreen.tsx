import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../../api/client";
import type { Schemas } from "../../../api/contract";
import { useLabelQueue, useSubmitLabel, type LabelTask } from "../../../api/evaluation";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { languageName } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { WithService } from "../../../shell/WithService";

type Strength = Schemas["FindingStrength"];

const ANSWERS: { shortcut: string; strength: Strength; label: string }[] = [
  { shortcut: "0", strength: "NONE", label: "No" },
  { shortcut: "1", strength: "WEAK", label: "Weak" },
  { shortcut: "2", strength: "MEDIUM", label: "Clear" },
  { shortcut: "3", strength: "STRONG", label: "Strong" },
];

// FR-145: one line, worded from the finding `strength` notes (sql-store.md).
const LEGEND =
  "No: no signal. Weak: mentioned or implied. Clear: stated. Strong: stated with commitment — " +
  "a programme, budget, target, date, hire or appointment.";

function taskKey(task: LabelTask): string {
  return `${task.chunk_id}:${task.question.id}`;
}

/** S-EVL-03: Labelling, `/labelling`, any signed-in user, the header's selected service
 * (`FR-003` after D12). WF-17. */
export function LabellingScreen() {
  return <WithService>{(service) => <LabellingTasks service={service} />}</WithService>;
}

function LabellingTasks({ service }: { service: Schemas["Service"] }) {
  const query = useLabelQueue(service.id);
  const submit = useSubmitLabel();
  const toast = useToast();
  // Skip is client-side, for the screen's lifetime; kept across a service change (G12, D10).
  const [handled, setHandled] = useState<Set<string>>(new Set());
  const [saveError, setSaveError] = useState<string | null>(null);
  const alreadyRefetchedRef = useRef(false);

  const tasks = query.data?.tasks ?? [];
  const visible = tasks.filter((task) => !handled.has(taskKey(task)));
  const current = visible[0];

  useEffect(() => {
    if (visible.length > 0) {
      alreadyRefetchedRef.current = false;
      return;
    }
    if (tasks.length > 0 && !alreadyRefetchedRef.current) {
      alreadyRefetchedRef.current = true;
      void query.refetch();
    }
  }, [visible.length, tasks.length, query]);

  const markHandled = useCallback((task: LabelTask) => {
    setHandled((prev) => new Set(prev).add(taskKey(task)));
  }, []);

  const handleSkip = useCallback(() => {
    if (current === undefined) {
      return;
    }
    markHandled(current);
  }, [current, markHandled]);

  const handleAnswer = useCallback(
    async (strength: Strength) => {
      if (current === undefined || submit.isPending) {
        return;
      }
      const task = current;
      try {
        await submit.mutateAsync({
          chunk_id: task.chunk_id,
          question_id: task.question.id,
          question_revision: task.question_revision,
          expected_strength: strength,
        });
        setSaveError(null);
        toast.notify("Label saved.");
        markHandled(task);
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          markHandled(task);
          await query.refetch();
          return;
        }
        setSaveError(error instanceof Error ? error.message : "The label could not be saved.");
      }
    },
    [current, submit, toast, markHandled, query],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (current === undefined) {
        return;
      }
      const answer = ANSWERS.find((entry) => entry.shortcut === event.key);
      if (answer !== undefined) {
        void handleAnswer(answer.strength);
        return;
      }
      if (event.key.toLowerCase() === "s") {
        handleSkip();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [current, handleAnswer, handleSkip]);

  return (
    <>
      <PageHeader
        title={`Labelling · ${service.name}`}
        lead="Say whether each passage shows the question's signal. The classifier's own answer is never shown."
        action={
          query.data === undefined ? null : (
            <LabelCount activeItems={query.data.active_items} minItems={query.data.min_items} />
          )
        }
      />
      <Callout kind="neutral">
        The classifier's answer is never shown here, so your label is not biased by it.
      </Callout>
      <DataView
        query={query}
        isEmpty={() => visible.length === 0}
        skeleton={<Skeleton className="h-80 w-full" />}
        empty={{
          message: "There is nothing left to label. Refresh more accounts to grow the queue.",
          action: <ButtonLink to="/accounts">Go to Accounts</ButtonLink>,
        }}
      >
        {() =>
          current === undefined ? null : (
            <div className="flex flex-col gap-4 rounded-card border border-border bg-surface p-6">
              <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                <dt className="font-medium text-text-secondary">Question</dt>
                <dd className="m-0">{current.question.text}</dd>
                <dt className="font-medium text-text-secondary">Company</dt>
                <dd className="m-0">{current.account.name}</dd>
                <dt className="font-medium text-text-secondary">Source</dt>
                <dd className="m-0 flex flex-wrap items-center gap-x-2">
                  {current.document.title !== null && (
                    <a
                      href={current.document.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent-ink underline"
                    >
                      {current.document.title} ↗
                    </a>
                  )}
                  <span className="text-text-secondary">
                    {languageName(current.document.language)}
                    {current.document.published_at !== null && (
                      <>
                        {" · "}
                        <RelativeTime at={current.document.published_at} />
                      </>
                    )}
                  </span>
                </dd>
              </dl>
              <div className="rounded-control bg-page p-4">
                <p className="m-0 whitespace-pre-wrap">{current.passage_text}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-text-secondary">Does this passage show it?</span>
                {ANSWERS.map((answer) => (
                  <Button key={answer.strength} onClick={() => void handleAnswer(answer.strength)}>
                    {`[${answer.shortcut}] ${answer.label}`}
                  </Button>
                ))}
                <Button variant="ghost" onClick={handleSkip}>
                  [S] Skip
                </Button>
              </div>
              <p className="m-0 text-hint text-text-tertiary">{LEGEND}</p>
              {saveError !== null && <Callout kind="error">{saveError}</Callout>}
            </div>
          )
        }
      </DataView>
    </>
  );
}

function LabelCount({ activeItems, minItems }: { activeItems: number; minItems: number }) {
  const percent = minItems <= 0 ? 100 : Math.min(100, Math.round((activeItems / minItems) * 100));
  const labelId = "label-count-progress-label";
  return (
    <div className="flex flex-col items-end gap-1">
      <span id={labelId} className="text-text-secondary">
        Labels: {activeItems} of {minItems} needed
      </span>
      <div
        role="progressbar"
        aria-labelledby={labelId}
        aria-valuenow={activeItems}
        aria-valuemin={0}
        aria-valuemax={minItems}
        className="h-2 w-40 overflow-hidden rounded-full bg-border"
      >
        <div className="h-full bg-accent" style={{ width: `${String(percent)}%` }} />
      </div>
    </div>
  );
}
