import { PlusIcon, XIcon } from "@phosphor-icons/react";
import { Link } from "react-router";
import { useState, type FormEvent } from "react";

import { useCreateQuestion, useUpdateQuestion } from "../../../api/servicesAndQuestions";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { CheckboxGroup } from "../../../components/CheckboxGroup";
import { Chip } from "../../../components/Chip";
import { FormField } from "../../../components/FormField";
import { Input, Select } from "../../../components/controls";
import { useToast } from "../../../components/Toast";
import { formErrors } from "../../../shell/formErrors";
import { enumLabel, strengthLabel } from "../../../shell/format";
import { toUpperSnakeInput } from "../../../shell/upperSnake";
import { willIncrementRevision, type QuestionFormShape } from "./questionForm";

type Question = Schemas["SignalQuestion"];
type AnswerType = Schemas["SignalQuestionAnswerType"];
type SourceType = Schemas["DocumentSourceType"];
type Option = Schemas["QuestionOption"];

const ANSWER_TYPES: AnswerType[] = ["YES_NO", "SCALE", "CHOICE"];
const SOURCE_TYPES: SourceType[] = ["NEWS", "COMPANY_PUBLICATION", "JOB_POSTING", "COMPANY_PROFILE"];
const STRENGTHS: Schemas["FindingStrength"][] = ["NONE", "WEAK", "MEDIUM", "STRONG"];
const MIN_CHOICE_OPTIONS = 2;
const FIELDS = ["key", "text", "answer_type", "options", "polarity", "source_types"] as const;

function emptyOption(): Option {
  return { key: "", label: "", strength: "NONE" };
}

function shapeOf(question: {
  text: string;
  answer_type: AnswerType;
  options: Option[] | null;
  source_types: SourceType[];
}): QuestionFormShape {
  return {
    text: question.text,
    answer_type: question.answer_type,
    options: question.options,
    source_types: question.source_types,
  };
}

interface QuestionFormProps {
  serviceId: string;
  /** Absent in Add mode; the question being edited otherwise. */
  question?: Question;
  onSaved: (question: Question) => void;
}

/**
 * FR-023 to FR-025, FR-150: one form for Add question and Edit. Try it (`FR-027`) is out of
 * scope (T16).
 */
export function QuestionForm({ serviceId, question, onSaved }: QuestionFormProps) {
  const editing = question !== undefined;
  const { notify } = useToast();
  const create = useCreateQuestion(serviceId);
  const update = useUpdateQuestion();
  const pending = create.isPending || update.isPending;
  const errors = formErrors(editing ? update.error : create.error, FIELDS);

  const [key, setKey] = useState(question?.key ?? "");
  const [text, setText] = useState(question?.text ?? "");
  const [answerType, setAnswerType] = useState<AnswerType>(question?.answer_type ?? "YES_NO");
  const [options, setOptions] = useState<Option[]>(question?.options ?? []);
  const [polarity, setPolarity] = useState<Schemas["SignalQuestionPolarity"]>(
    question?.polarity ?? "POSITIVE",
  );
  const [sourceTypes, setSourceTypes] = useState<SourceType[]>(question?.source_types ?? []);
  const [hintTerms, setHintTerms] = useState<string[]>(question?.hint_terms ?? []);
  const [hintDraft, setHintDraft] = useState("");

  const revisionWarning =
    editing && willIncrementRevision(shapeOf(question), shapeOf({ text, answer_type: answerType, options: answerType === "CHOICE" ? options : null, source_types: sourceTypes }));

  function setAnswer(next: AnswerType) {
    setAnswerType(next);
    if (next !== "CHOICE") {
      setOptions([]);
    } else if (options.length === 0) {
      setOptions([emptyOption(), emptyOption()]);
    }
  }

  function addHintTerm() {
    const term = hintDraft.trim();
    if (term !== "" && !hintTerms.includes(term)) {
      setHintTerms([...hintTerms, term]);
    }
    setHintDraft("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const effectiveOptions = answerType === "CHOICE" ? options : null;
    if (!editing) {
      create.mutate(
        {
          key,
          text,
          answer_type: answerType,
          ...(effectiveOptions !== null && { options: effectiveOptions }),
          polarity,
          source_types: sourceTypes,
          hint_terms: hintTerms,
        },
        { onSuccess: onSaved },
      );
      return;
    }
    const body: Schemas["SignalQuestionUpdate"] = {
      ...(text !== question.text && { text }),
      ...(answerType !== question.answer_type && { answer_type: answerType }),
      ...(answerType === "CHOICE" &&
        JSON.stringify(effectiveOptions) !== JSON.stringify(question.options) && {
          options: effectiveOptions,
        }),
      ...(JSON.stringify(sourceTypes) !== JSON.stringify(question.source_types) && {
        source_types: sourceTypes,
      }),
      ...(JSON.stringify(hintTerms) !== JSON.stringify(question.hint_terms) && {
        hint_terms: hintTerms,
      }),
    };
    if (Object.keys(body).length === 0) {
      return;
    }
    update.mutate(
      { id: question.id, body },
      {
        onSuccess: (saved) => {
          notify(`Revision ${String(saved.revision)} saved`);
          onSaved(saved);
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="num m-0 text-section font-semibold">{editing ? question.key : "New question"}</h3>
        {editing && <Chip tone="neutral">{`Revision ${String(question.revision)}`}</Chip>}
      </div>
      {!editing && (
        <FormField label="Key" hint="UPPER_SNAKE. Cannot be changed later." error={errors.fields["key"]}>
          {(field) => (
            <Input
              {...field}
              type="text"
              value={key}
              onChange={(event) => {
                setKey(toUpperSnakeInput(event.target.value));
              }}
            />
          )}
        </FormField>
      )}
      <FormField label="Question" error={errors.fields["text"]}>
        {(field) => (
          <Input
            {...field}
            type="text"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
            }}
          />
        )}
      </FormField>
      <fieldset className="flex flex-col gap-1.5 border-0 p-0 m-0">
        <legend className="p-0 font-medium">Answer type</legend>
        <div className="flex gap-4">
          {ANSWER_TYPES.map((type) => (
            <label key={type} className="flex items-center gap-1.5">
              <input
                type="radio"
                name="answer_type"
                checked={answerType === type}
                onChange={() => {
                  setAnswer(type);
                }}
              />
              {enumLabel(type)}
            </label>
          ))}
        </div>
      </fieldset>
      {answerType === "CHOICE" && (
        <OptionsEditor options={options} onChange={setOptions} error={errors.fields["options"]} />
      )}
      <FormField label="Polarity">
        {() =>
          editing ? (
            <p className="m-0">{`${enumLabel(polarity)} (fixed)`}</p>
          ) : (
            <Select
              value={polarity}
              onChange={(event) => {
                setPolarity(event.target.value as Schemas["SignalQuestionPolarity"]);
              }}
            >
              <option value="POSITIVE">Positive</option>
              <option value="NEGATIVE">Negative</option>
            </Select>
          )
        }
      </FormField>
      <CheckboxGroup
        label="Source types"
        options={SOURCE_TYPES.map((type) => ({ value: type, label: enumLabel(type) }))}
        selected={sourceTypes}
        onChange={(values) => {
          setSourceTypes(values as SourceType[]);
        }}
        error={errors.fields["source_types"]}
      />
      <div className="flex flex-col gap-1.5">
        <span className="font-medium">Hint terms</span>
        <div className="flex flex-wrap items-center gap-2">
          {hintTerms.map((term) => (
            <Chip key={term}>
              {term}
              <button
                type="button"
                aria-label={`Remove ${term}`}
                onClick={() => {
                  setHintTerms(hintTerms.filter((entry) => entry !== term));
                }}
              >
                <XIcon size={12} aria-hidden />
              </button>
            </Chip>
          ))}
          <Input
            type="text"
            value={hintDraft}
            placeholder="Add a hint term"
            className="w-40"
            onChange={(event) => {
              setHintDraft(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addHintTerm();
              }
            }}
          />
          <Button type="button" variant="secondary" size="small" onClick={addHintTerm}>
            <PlusIcon size={14} aria-hidden />
          </Button>
        </div>
        <span className="text-hint text-text-tertiary">
          Hint terms only steer searching; they do not change the revision.
        </span>
      </div>
      {revisionWarning === true && (
        <Callout kind="caution">
          Saving will increment the revision and re-check stored data.
        </Callout>
      )}
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={pending}>
          Save
        </Button>
      </div>
    </form>
  );
}

function OptionsEditor({
  options,
  onChange,
  error,
}: {
  options: Option[];
  onChange: (options: Option[]) => void;
  error?: string | undefined;
}) {
  function update(index: number, patch: Partial<Option>) {
    onChange(options.map((option, i) => (i === index ? { ...option, ...patch } : option)));
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="font-medium">Options</span>
      {options.map((option, index) => (
        <div key={index} className="flex items-center gap-2">
          <Input
            type="text"
            aria-label={`Option ${String(index + 1)} key`}
            value={option.key}
            placeholder="KEY"
            className="w-28"
            onChange={(event) => {
              update(index, { key: toUpperSnakeInput(event.target.value) });
            }}
          />
          <Input
            type="text"
            aria-label={`Option ${String(index + 1)} label`}
            value={option.label}
            placeholder="Label"
            onChange={(event) => {
              update(index, { label: event.target.value });
            }}
          />
          <Select
            aria-label={`Option ${String(index + 1)} strength`}
            value={option.strength}
            onChange={(event) => {
              update(index, { strength: event.target.value as Schemas["FindingStrength"] });
            }}
          >
            {STRENGTHS.map((strength) => (
              <option key={strength} value={strength}>
                {strengthLabel(strength)}
              </option>
            ))}
          </Select>
          {options.length > MIN_CHOICE_OPTIONS && (
            <Button
              type="button"
              variant="ghost"
              size="small"
              aria-label={`Remove option ${String(index + 1)}`}
              onClick={() => {
                onChange(options.filter((_, i) => i !== index));
              }}
            >
              <XIcon size={14} aria-hidden />
            </Button>
          )}
        </div>
      ))}
      <Button
        type="button"
        variant="secondary"
        size="small"
        className="self-start"
        onClick={() => {
          onChange([...options, emptyOption()]);
        }}
      >
        <PlusIcon size={14} aria-hidden />
        Add option
      </Button>
      {error !== undefined && <span className="text-hint text-negative">{error}</span>}
    </div>
  );
}

export { Link as _unusedLinkImportGuard };
