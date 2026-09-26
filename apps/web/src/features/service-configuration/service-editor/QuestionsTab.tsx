/**
 * `FR-022`, `FR-150`: the two-pane Signal questions tab - the list at the left, the selected
 * question's form at the right. [Try it](/features/service-configuration.md#service-editor)
 * (`S-CFG-05`) is owned by a later task.
 */
import { PlusCircleIcon, MinusCircleIcon } from "@phosphor-icons/react";
import { useState } from "react";

import { ApiError } from "../../../api/client";
import { useQuestions, useUpdateQuestion, type SignalQuestion } from "../../../api/services";
import { Button } from "../../../components/Button";
import { ConfirmDialog } from "../../../components/Dialog";
import { EmptyState, ErrorState, UnavailableState } from "../../../components/States";
import { useToast } from "../../../components/Toast";
import { titleCaseEnum } from "../../../shell/formatting";
import { QuestionForm } from "./QuestionForm";

type ConfirmState = { action: "deactivate" | "reactivate"; question: SignalQuestion } | null;
type Selection = { mode: "create" } | { mode: "edit"; id: string } | null;

export function QuestionsTab({ serviceId }: { serviceId: string }) {
  const { data: questions, isLoading, isError, error, refetch } = useQuestions(serviceId);
  const [selection, setSelection] = useState<Selection>(null);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const updateQuestion = useUpdateQuestion();
  const { showToast } = useToast();

  if (isLoading) {
    return <div className="h-40 rounded-card bg-page" />;
  }
  if (isError) {
    if (error instanceof ApiError && (error.status === 503 || error.status === 429)) {
      return (
        <UnavailableState
          dependency={
            typeof error.details?.dependency === "string"
              ? error.details.dependency
              : "The database"
          }
          stillWorks={[]}
        />
      );
    }
    return (
      <ErrorState
        message={error instanceof ApiError ? error.message : "Something went wrong."}
        onRetry={() => void refetch()}
      />
    );
  }

  const sorted = [...(questions ?? [])].sort((a, b) => {
    if (a.status !== b.status) {
      return a.status === "ACTIVE" ? -1 : 1;
    }
    return a.key.localeCompare(b.key);
  });

  const selected =
    selection?.mode === "edit" ? (sorted.find((q) => q.id === selection.id) ?? null) : null;

  const handleConfirmToggle = () => {
    if (confirm === null) {
      return;
    }
    updateQuestion.mutate(
      {
        id: confirm.question.id,
        body: { status: confirm.action === "deactivate" ? "INACTIVE" : "ACTIVE" },
      },
      {
        onSuccess: () => {
          showToast(
            confirm.action === "deactivate"
              ? `${confirm.question.key} was deactivated.`
              : `${confirm.question.key} was reactivated.`,
          );
          setConfirm(null);
        },
      },
    );
  };

  return (
    <div className="grid grid-cols-[280px_1fr] gap-6">
      <div className="flex flex-col gap-3">
        <Button
          variant="secondary"
          onClick={() => {
            setSelection({ mode: "create" });
          }}
        >
          Add question
        </Button>
        {sorted.length === 0 && (
          <EmptyState
            message="No signal questions yet. Add the first one this service asks of every passage."
            actionLabel="Add question"
            onAction={() => {
              setSelection({ mode: "create" });
            }}
          />
        )}
        <ul className="flex flex-col gap-1">
          {sorted.map((question) => (
            <li key={question.id}>
              <button
                type="button"
                onClick={() => {
                  setSelection({ mode: "edit", id: question.id });
                }}
                className={`flex w-full items-center gap-2 rounded-control border px-3 py-2 text-left text-sm ${
                  selection?.mode === "edit" && selection.id === question.id
                    ? "border-accent bg-accent-soft text-accent-ink"
                    : "border-border bg-surface text-text hover:bg-page"
                }`}
              >
                {question.polarity === "POSITIVE" ? (
                  <PlusCircleIcon
                    size={16}
                    weight="fill"
                    className="text-positive"
                    aria-hidden="true"
                  />
                ) : (
                  <MinusCircleIcon
                    size={16}
                    weight="fill"
                    className="text-negative"
                    aria-hidden="true"
                  />
                )}
                <span className="flex-1 truncate">
                  <span className="font-mono text-[12.5px]">{question.key}</span>
                  <span className="ml-2 truncate text-text-secondary">{question.text}</span>
                </span>
                <span className="shrink-0 text-[12.5px] text-text-tertiary">
                  {titleCaseEnum(question.answer_type)} · {question.finding_count}
                </span>
              </button>
              <div className="mt-1 flex justify-end">
                <Button
                  variant="ghost"
                  size="small"
                  onClick={() => {
                    setConfirm({
                      action: question.status === "ACTIVE" ? "deactivate" : "reactivate",
                      question,
                    });
                  }}
                >
                  {question.status === "ACTIVE" ? "Deactivate" : "Reactivate"}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <div>
        {selection === null && (
          <p className="text-sm text-text-secondary">Select a question, or add a new one.</p>
        )}
        {selection?.mode === "create" && (
          <QuestionForm
            key="new"
            serviceId={serviceId}
            question={null}
            onSaved={(created) => {
              setSelection({ mode: "edit", id: created.id });
            }}
          />
        )}
        {selected !== null && (
          <QuestionForm
            key={selected.id}
            serviceId={serviceId}
            question={selected}
            onSaved={() => {
              // Stays on the same question; the list refetches from the invalidated query.
            }}
          />
        )}
      </div>

      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open) {
            setConfirm(null);
          }
        }}
        title={confirm?.action === "deactivate" ? "Deactivate question" : "Reactivate question"}
        description={
          confirm?.action === "deactivate" ? (
            <>
              {confirm.question.key} leaves the draft; its signals stop counting once a scoring
              version without it is activated.
            </>
          ) : (
            <>
              {confirm?.question.key} rejoins the draft; its signals count once a scoring version
              with it is activated.
            </>
          )
        }
        confirmLabel={
          confirm?.action === "deactivate" ? "Deactivate question" : "Reactivate question"
        }
        onConfirm={handleConfirmToggle}
        confirmPending={updateQuestion.isPending}
      />
    </div>
  );
}
