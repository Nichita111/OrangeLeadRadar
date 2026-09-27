import { PlusIcon, XIcon } from "@phosphor-icons/react";
import { useState } from "react";

import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { strengthLabel } from "../../../shell/format";
import { DisqualifierDialog } from "./DisqualifierDialog";

type ScoringSettings = Schemas["ScoringSettings"];
type Disqualifier = Schemas["Disqualifier"];

function operandSummary(disqualifier: Disqualifier): string {
  return disqualifier.kind === "ICP_MISMATCH"
    ? (disqualifier.criterion_key ?? "")
    : `${disqualifier.question_key ?? ""} ≥ ${strengthLabel(disqualifier.min_strength ?? "WEAK")}`;
}

interface ExclusionsProps {
  settings: ScoringSettings;
  onChange: (next: ScoringSettings) => void;
  questions: Schemas["SignalQuestion"][];
  errors: Partial<Record<string, string>>;
}

/** FR-032, G5: lists the exclusion rules and adds or edits one. */
export function Exclusions({ settings, onChange, questions, errors }: ExclusionsProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  function save(index: number | null, disqualifier: Disqualifier) {
    const disqualifiers =
      index === null
        ? [...settings.disqualifiers, disqualifier]
        : settings.disqualifiers.map((entry, i) => (i === index ? disqualifier : entry));
    onChange({ ...settings, disqualifiers });
  }

  function remove(index: number) {
    onChange({ ...settings, disqualifiers: settings.disqualifiers.filter((_, i) => i !== index) });
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="font-medium">Exclusion rules</span>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {settings.disqualifiers.map((disqualifier, index) => {
          const pointer = `/disqualifiers/${String(index)}`;
          return (
            <li
              key={disqualifier.key}
              className="flex items-center gap-2 rounded-control px-2.5 py-1.5"
            >
              <span className="num w-24 shrink-0 font-medium">{disqualifier.key}</span>
              <span className="min-w-0 flex-1 truncate">
                {disqualifier.label} — {operandSummary(disqualifier)}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="small"
                onClick={() => {
                  setEditingIndex(index);
                }}
              >
                Edit
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="small"
                aria-label={`Remove exclusion rule ${disqualifier.key}`}
                onClick={() => {
                  remove(index);
                }}
              >
                <XIcon size={14} aria-hidden />
              </Button>
              {(errors[`${pointer}/criterion_key`] ?? errors[`${pointer}/question_key`]) !==
                undefined && (
                <span className="text-hint text-negative">
                  {errors[`${pointer}/criterion_key`] ?? errors[`${pointer}/question_key`]}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {editingIndex !== null && (
        <DisqualifierDialog
          open
          onOpenChange={(next) => {
            if (!next) {
              setEditingIndex(null);
            }
          }}
          disqualifier={settings.disqualifiers[editingIndex]}
          criteria={settings.icp_criteria}
          questions={questions}
          onSave={(disqualifier) => {
            save(editingIndex, disqualifier);
          }}
        />
      )}
      <DisqualifierDialog
        trigger={
          <Button type="button" variant="secondary" size="small" className="self-start">
            <PlusIcon size={14} aria-hidden />
            Add exclusion rule
          </Button>
        }
        criteria={settings.icp_criteria}
        questions={questions}
        onSave={(disqualifier) => {
          save(null, disqualifier);
        }}
      />
    </div>
  );
}
