import { MinusCircleIcon, PlusCircleIcon } from "@phosphor-icons/react";

import type { Schemas } from "../../../api/contract";
import { Select, Input } from "../../../components/controls";
import { WEIGHT_LEVELS } from "../../../shell/enumValues";
import { enumLabel } from "../../../shell/format";
import { halfLifePlaceholder } from "./scoringDraft";

type ScoringSettings = Schemas["ScoringSettings"];
type SignalQuestion = Schemas["SignalQuestion"];

interface SignalsSectionProps {
  settings: ScoringSettings;
  onChange: (next: ScoringSettings) => void;
  questions: SignalQuestion[];
  errors: Partial<Record<string, string>>;
}

/** FR-031: every active question, its polarity, a weight select and an optional half-life. */
export function SignalsSection({ settings, onChange, questions, errors }: SignalsSectionProps) {
  function settingFor(key: string) {
    return settings.questions.find((setting) => setting.question_key === key);
  }

  function update(key: string, patch: Partial<Schemas["QuestionSetting"]>) {
    onChange({
      ...settings,
      questions: settings.questions.map((setting) =>
        setting.question_key === key ? { ...setting, ...patch } : setting,
      ),
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="font-medium">Signals</span>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {questions
          .filter((question) => question.status === "ACTIVE")
          .map((question) => {
            const setting = settingFor(question.key);
            const PolarityIcon =
              question.polarity === "POSITIVE" ? PlusCircleIcon : MinusCircleIcon;
            // The document index, not the position in this filtered list: the pointer a
            // `VALIDATION` error names is `/questions/<index in settings.questions>` (FR-034).
            const documentIndex = settings.questions.findIndex(
              (item) => item.question_key === question.key,
            );
            const pointer = `/questions/${String(documentIndex)}`;
            return (
              <li key={question.key} className="flex items-center gap-2 py-1">
                <PolarityIcon
                  size={16}
                  weight="fill"
                  role="img"
                  aria-label={question.polarity === "POSITIVE" ? "Positive" : "Negative"}
                  className={question.polarity === "POSITIVE" ? "text-positive" : "text-negative"}
                />
                <span className="num min-w-0 flex-1 truncate font-medium">{question.key}</span>
                <Select
                  aria-label={`${question.key} weight`}
                  value={setting?.weight ?? "MEDIUM"}
                  onChange={(event) => {
                    update(question.key, { weight: event.target.value as Schemas["WeightLevel"] });
                  }}
                >
                  {WEIGHT_LEVELS.map((weight) => (
                    <option key={weight} value={weight}>
                      {enumLabel(weight)}
                    </option>
                  ))}
                </Select>
                <Input
                  type="number"
                  aria-label={`${question.key} half-life days`}
                  className="w-24"
                  placeholder={halfLifePlaceholder(
                    question.source_types,
                    settings.default_half_life_days,
                  )}
                  value={setting?.half_life_days ?? ""}
                  onChange={(event) => {
                    update(question.key, {
                      half_life_days: event.target.value === "" ? null : Number(event.target.value),
                    });
                  }}
                />
                {errors[`${pointer}/weight`] !== undefined && (
                  <span className="text-hint text-negative">{errors[`${pointer}/weight`]}</span>
                )}
              </li>
            );
          })}
      </ul>
      {errors["/questions"] !== undefined && (
        <span className="text-hint text-negative">{errors["/questions"]}</span>
      )}
    </div>
  );
}
