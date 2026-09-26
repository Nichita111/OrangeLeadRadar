/**
 * `FR-023`, `FR-024`, `FR-025`: one form for Add question and Edit. [Try it](#fl-03-try-a-question)
 * (`S-CFG-05`) is owned by a later task, so this form ends at Save.
 */
import { PlusIcon, TrashIcon } from "@phosphor-icons/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  useCreateQuestion,
  useUpdateQuestion,
  type DocumentSourceType,
  type QuestionOption,
  type SignalQuestion,
  type SignalQuestionAnswerType,
  type SignalQuestionPolarity,
} from "../../../api/services";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { CheckboxGroup } from "../../../components/CheckboxGroup";
import { Input } from "../../../components/Input";
import { Select } from "../../../components/Select";
import { Textarea } from "../../../components/Textarea";
import { strengthLabel, titleCaseEnum } from "../../../shell/formatting";
import { fieldErrorsOf, formLevelError } from "../../identity-and-access/users/field-errors";

const ANSWER_TYPE_OPTIONS: { value: SignalQuestionAnswerType; label: string }[] = [
  { value: "YES_NO", label: "Yes/no" },
  { value: "SCALE", label: "Scale" },
  { value: "CHOICE", label: "Choice" },
];

const POLARITY_OPTIONS: { value: SignalQuestionPolarity; label: string }[] = [
  { value: "POSITIVE", label: "Positive" },
  { value: "NEGATIVE", label: "Negative" },
];

const SOURCE_TYPE_OPTIONS: { value: DocumentSourceType; label: string }[] = [
  { value: "NEWS", label: "News" },
  { value: "COMPANY_PUBLICATION", label: "Company publication" },
  { value: "JOB_POSTING", label: "Job posting" },
  { value: "COMPANY_PROFILE", label: "Company profile" },
];

const STRENGTH_SELECT_OPTIONS = ["NONE", "WEAK", "MEDIUM", "STRONG"].map((value) => ({
  value,
  label: strengthLabel(value),
}));

function defaultOptions(): QuestionOption[] {
  return [
    { key: "YES", label: "Yes", strength: "STRONG" },
    { key: "NO", label: "No", strength: "NONE" },
  ];
}

function sourceTypesChanged(a: DocumentSourceType[], b: DocumentSourceType[]): boolean {
  if (a.length !== b.length) {
    return true;
  }
  const sortedA = [...a].sort();
  const sortedB = [...b].sort();
  return sortedA.some((value, index) => value !== sortedB[index]);
}

function optionsChanged(a: QuestionOption[] | null, b: QuestionOption[] | null): boolean {
  if (a === null || b === null) {
    return a !== b;
  }
  if (a.length !== b.length) {
    return true;
  }
  return a.some((option, index) => {
    const other = b[index];
    return (
      other === undefined ||
      option.key !== other.key ||
      option.label !== other.label ||
      option.strength !== other.strength
    );
  });
}

export interface QuestionFormProps {
  serviceId: string;
  /** `null` starts a new question ([FR-023](/features/service-configuration.md#service-editor)). */
  question: SignalQuestion | null;
  onSaved: (question: SignalQuestion) => void;
}

export function QuestionForm({ serviceId, question, onSaved }: QuestionFormProps) {
  const [key, setKey] = useState(question?.key ?? "");
  const [text, setText] = useState(question?.text ?? "");
  const [answerType, setAnswerType] = useState<SignalQuestionAnswerType>(
    question?.answer_type ?? "YES_NO",
  );
  const [options, setOptions] = useState<QuestionOption[]>(
    question?.options ?? (question?.answer_type === "CHOICE" ? [] : defaultOptions()),
  );
  const [polarity, setPolarity] = useState<SignalQuestionPolarity>(
    question?.polarity ?? "POSITIVE",
  );
  const [sourceTypes, setSourceTypes] = useState<DocumentSourceType[]>(
    question?.source_types ?? [],
  );
  const [hintTerms, setHintTerms] = useState<string[]>(question?.hint_terms ?? []);
  const [hintDraft, setHintDraft] = useState("");
  const [justSaved, setJustSaved] = useState(false);

  const createQuestion = useCreateQuestion(serviceId);
  const updateQuestion = useUpdateQuestion();
  const pending = createQuestion.isPending || updateQuestion.isPending;
  const mutationError = createQuestion.error ?? updateQuestion.error;
  const errors = fieldErrorsOf(mutationError);
  const topLevelError = formLevelError(mutationError, errors);

  const effectiveOptions = answerType === "CHOICE" ? options : null;
  const willReclassify =
    question === null ||
    text !== question.text ||
    answerType !== question.answer_type ||
    optionsChanged(effectiveOptions, question.options) ||
    sourceTypesChanged(sourceTypes, question.source_types);

  const addHintTerm = () => {
    const term = hintDraft.trim();
    if (term.length === 0 || hintTerms.includes(term)) {
      return;
    }
    setHintTerms([...hintTerms, term]);
    setHintDraft("");
  };

  const addOption = () => {
    setOptions([...options, { key: "", label: "", strength: "NONE" }]);
  };

  const updateOption = (index: number, patch: Partial<QuestionOption>) => {
    setOptions(options.map((option, i) => (i === index ? { ...option, ...patch } : option)));
  };

  const removeOption = (index: number) => {
    setOptions(options.filter((_, i) => i !== index));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setJustSaved(false);
    if (question === null) {
      createQuestion.mutate(
        {
          key,
          text,
          answer_type: answerType,
          options: effectiveOptions,
          polarity,
          source_types: sourceTypes,
          hint_terms: hintTerms,
        },
        {
          onSuccess: (created) => {
            setJustSaved(true);
            onSaved(created);
          },
        },
      );
      return;
    }
    updateQuestion.mutate(
      {
        id: question.id,
        body: {
          text,
          answer_type: answerType,
          options: effectiveOptions,
          source_types: sourceTypes,
          hint_terms: hintTerms,
        },
      },
      {
        onSuccess: (updated) => {
          setJustSaved(true);
          onSaved(updated);
        },
      },
    );
  };

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
      {topLevelError !== null && <Callout kind="error">{topLevelError}</Callout>}
      {justSaved && (
        <Callout kind="accent">
          Saved as revision {question?.revision ?? 1}.
          {willReclassify && (
            <>
              {" "}
              A reclassification run was queued; see it on{" "}
              <Link to="/runs" className="underline">
                Runs
              </Link>
              .
            </>
          )}
        </Callout>
      )}
      {question === null ? (
        <Input
          id="question-key"
          label="Key"
          hint="UPPER_SNAKE, unique within the service. Cannot be changed later."
          value={key}
          onChange={(event) => {
            setKey(event.target.value.toUpperCase());
          }}
          error={errors.key}
          required
        />
      ) : (
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm text-text">{question.key}</span>
          <span className="text-[12.5px] text-text-tertiary">Revision {question.revision}</span>
        </div>
      )}
      <Textarea
        id="question-text"
        label="Question text"
        hint="Answerable from one passage, in English."
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
        error={errors.text}
        required
      />
      <Select
        id="question-answer-type"
        label="Answer type"
        value={answerType}
        onValueChange={(value) => {
          const next = value as SignalQuestionAnswerType;
          setAnswerType(next);
          if (next === "CHOICE" && options.length === 0) {
            setOptions(defaultOptions());
          }
        }}
        options={ANSWER_TYPE_OPTIONS}
        error={errors.answer_type}
      />
      {answerType === "CHOICE" && (
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium text-text">Options</span>
          {options.map((option, index) => (
            <div key={index} className="flex items-end gap-2">
              <Input
                id={`question-option-key-${String(index)}`}
                label="Key"
                value={option.key}
                onChange={(event) => {
                  updateOption(index, { key: event.target.value.toUpperCase() });
                }}
              />
              <Input
                id={`question-option-label-${String(index)}`}
                label="Label"
                value={option.label}
                onChange={(event) => {
                  updateOption(index, { label: event.target.value });
                }}
              />
              <Select
                id={`question-option-strength-${String(index)}`}
                label="Strength"
                value={option.strength}
                onValueChange={(value) => {
                  updateOption(index, { strength: value as QuestionOption["strength"] });
                }}
                options={STRENGTH_SELECT_OPTIONS}
              />
              <Button
                type="button"
                variant="ghost"
                size="small"
                aria-label={`Remove option ${String(index + 1)}`}
                onClick={() => {
                  removeOption(index);
                }}
              >
                <TrashIcon size={16} aria-hidden="true" />
              </Button>
            </div>
          ))}
          {errors.options !== undefined && (
            <p role="alert" className="text-[12.5px] text-negative">
              {errors.options}
            </p>
          )}
          <Button type="button" variant="secondary" size="small" onClick={addOption}>
            <PlusIcon size={16} aria-hidden="true" /> Option
          </Button>
        </div>
      )}
      {question === null ? (
        <Select
          id="question-polarity"
          label="Polarity"
          value={polarity}
          onValueChange={(value) => {
            setPolarity(value as SignalQuestionPolarity);
          }}
          options={POLARITY_OPTIONS}
          hint="Positive findings raise Intent, negative findings lower it. Cannot be changed later."
        />
      ) : (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-text">Polarity</span>
          <p className="text-sm text-text-secondary">{titleCaseEnum(question.polarity)} (fixed)</p>
        </div>
      )}
      <CheckboxGroup
        id="question-source-types"
        label="Sources"
        options={SOURCE_TYPE_OPTIONS}
        selected={sourceTypes}
        onChange={(values) => {
          setSourceTypes(values as DocumentSourceType[]);
        }}
        error={errors.source_types}
      />
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-text">Hint terms</span>
        <div className="flex flex-wrap gap-1.5">
          {hintTerms.map((term) => (
            <span
              key={term}
              className="inline-flex items-center gap-1 rounded-full bg-page px-2.5 py-1 text-[12.5px] text-text-secondary"
            >
              {term}
              <button
                type="button"
                aria-label={`Remove ${term}`}
                onClick={() => {
                  setHintTerms(hintTerms.filter((entry) => entry !== term));
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={hintDraft}
            onChange={(event) => {
              setHintDraft(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addHintTerm();
              }
            }}
            aria-label="New hint term"
            className="flex-1 rounded-control border border-border bg-surface px-3 text-sm text-text focus-visible:outline-none"
            style={{ height: "var(--ctl-input)" }}
          />
          <Button type="button" variant="secondary" onClick={addHintTerm}>
            Add
          </Button>
        </div>
        <p className="text-[12.5px] leading-snug text-text-tertiary">
          Hint terms only steer searching; they never decide an answer.
        </p>
      </div>
      {willReclassify && (
        <Callout kind="caution">
          Saving will {question === null ? "" : "increment the revision and "}re-check stored
          passages for this question.
        </Callout>
      )}
      <div className="mt-2 flex justify-end gap-2">
        <Button type="submit" variant="primary" disabled={pending}>
          {question === null ? "Create question" : "Save"}
        </Button>
      </div>
    </form>
  );
}
