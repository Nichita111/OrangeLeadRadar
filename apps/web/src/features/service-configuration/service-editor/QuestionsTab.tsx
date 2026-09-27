import { MinusCircleIcon, PlusCircleIcon, PlusIcon } from "@phosphor-icons/react";
import { useState } from "react";

import { useQuestions, useUpdateQuestion } from "../../../api/servicesAndQuestions";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { RowMenu } from "../../../components/RowMenu";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { enumLabel } from "../../../shell/format";
import { DataView } from "../../../shell/states/DataView";
import { QuestionForm } from "./QuestionForm";

type Question = Schemas["SignalQuestion"];
type Selection = { mode: "add" } | { mode: "edit"; id: string };

const DEACTIVATE_NOTE = "signals stop counting once scoring without it is activated.";

function SkeletonList() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-16 w-full" />
      ))}
    </div>
  );
}

/** FR-022, FR-150: the list of the service's questions and the selected question's form. */
export function QuestionsTab({ serviceId }: { serviceId: string }) {
  const questions = useQuestions(serviceId);
  const [selection, setSelection] = useState<Selection | null>(null);

  return (
    <DataView
      query={questions}
      isEmpty={() => false}
      skeleton={<SkeletonList />}
      empty={{ message: "", action: null }}
    >
      {(rows) => {
        const first = rows[0];
        const effective: Selection =
          selection ?? (first !== undefined ? { mode: "edit", id: first.id } : { mode: "add" });
        const selected =
          effective.mode === "edit" ? rows.find((row) => row.id === effective.id) : undefined;
        const formKey = effective.mode === "edit" ? effective.id : "add";

        return (
          <div className="grid grid-cols-[320px_1fr] gap-6">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="m-0 text-section font-semibold">Signal questions</h3>
                <Button
                  variant="secondary"
                  size="small"
                  onClick={() => {
                    setSelection({ mode: "add" });
                  }}
                >
                  <PlusIcon size={14} aria-hidden />
                  Add question
                </Button>
              </div>
              {rows.length === 0 && (
                <p className="m-0 text-text-secondary">No questions yet. Add the first one.</p>
              )}
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {rows.map((question) => (
                  <QuestionRow
                    key={question.id}
                    question={question}
                    active={effective.mode === "edit" && effective.id === question.id}
                    onSelect={() => {
                      setSelection({ mode: "edit", id: question.id });
                    }}
                  />
                ))}
              </ul>
            </div>
            <QuestionForm
              key={formKey}
              serviceId={serviceId}
              {...(selected === undefined ? {} : { question: selected })}
              onSaved={(saved) => {
                setSelection({ mode: "edit", id: saved.id });
              }}
            />
          </div>
        );
      }}
    </DataView>
  );
}

function QuestionRow({
  question,
  active,
  onSelect,
}: {
  question: Question;
  active: boolean;
  onSelect: () => void;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const update = useUpdateQuestion();
  const { notify } = useToast();
  const isActive = question.status === "ACTIVE";
  const PolarityIcon = question.polarity === "POSITIVE" ? PlusCircleIcon : MinusCircleIcon;

  return (
    <li>
      <div
        className={`flex items-center gap-2 rounded-control px-2.5 py-2 ${active ? "bg-accent-soft" : "hover:bg-page"}`}
      >
        <button
          type="button"
          onClick={onSelect}
          aria-current={active ? "true" : undefined}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <PolarityIcon
            size={16}
            weight="fill"
            role="img"
            aria-label={question.polarity === "POSITIVE" ? "Positive" : "Negative"}
            className={question.polarity === "POSITIVE" ? "text-positive" : "text-negative"}
          />
          <span className="flex min-w-0 flex-col">
            <span className="num truncate font-medium">{question.key}</span>
            <span className="truncate text-hint text-text-secondary">{question.text}</span>
          </span>
        </button>
        <span className="shrink-0 text-hint text-text-tertiary">
          {enumLabel(question.answer_type)}
        </span>
        <span className="num shrink-0 text-hint text-text-tertiary">{question.finding_count}</span>
        <RowMenu
          label={`Actions for ${question.key}`}
          items={[
            {
              label: isActive ? "Deactivate" : "Reactivate",
              onSelect: () => {
                setConfirmOpen(true);
              },
            },
          ]}
        />
        <ConfirmDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          title={isActive ? "Deactivate question" : "Reactivate question"}
          description={`${question.key} ${isActive ? DEACTIVATE_NOTE : "will count towards scoring again."}`}
          confirmLabel={isActive ? "Deactivate question" : "Reactivate question"}
          onConfirm={() => {
            update.mutate(
              { id: question.id, body: { status: isActive ? "INACTIVE" : "ACTIVE" } },
              {
                onSuccess: () => {
                  notify(isActive ? "Question deactivated" : "Question reactivated");
                },
              },
            );
          }}
        />
      </div>
    </li>
  );
}
