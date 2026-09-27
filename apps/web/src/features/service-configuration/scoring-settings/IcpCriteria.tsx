import { PlusIcon, XIcon } from "@phosphor-icons/react";
import { useState } from "react";

import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { enumLabel } from "../../../shell/format";
import { CriterionDialog } from "./CriterionDialog";
import { retiredIndustryCodes } from "./scoringDraft";

type ScoringSettings = Schemas["ScoringSettings"];
type ICPCriterion = Schemas["ICPCriterion"];

function operandSummary(criterion: ICPCriterion): string {
  if (criterion.kind === "EMPLOYEE_RANGE" || criterion.kind === "REVENUE_RANGE") {
    return criterion.max === null || criterion.max === undefined
      ? `≥ ${String(criterion.min ?? 0)}`
      : `${String(criterion.min ?? 0)}–${String(criterion.max)}`;
  }
  return (criterion.values ?? []).join(", ");
}

interface IcpCriteriaProps {
  settings: ScoringSettings;
  onChange: (next: ScoringSettings) => void;
  industries: Schemas["Industry"][];
  markets: Schemas["Market"][];
  errors: Partial<Record<string, string>>;
}

/** FR-030: lists the ICP criteria and adds or edits one; marks a retired industry. */
export function IcpCriteria({ settings, onChange, industries, markets, errors }: IcpCriteriaProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const editingCriterion = editingIndex === null ? undefined : settings.icp_criteria[editingIndex];
  const retired = retiredIndustryCodes(settings.icp_criteria, industries);

  function save(index: number | null, criterion: ICPCriterion) {
    const criteria =
      index === null
        ? [...settings.icp_criteria, criterion]
        : settings.icp_criteria.map((entry, i) => (i === index ? criterion : entry));
    onChange({ ...settings, icp_criteria: criteria });
  }

  function remove(index: number) {
    onChange({
      ...settings,
      icp_criteria: settings.icp_criteria.filter((_, i) => i !== index),
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="font-medium">ICP</span>
      {retired.length > 0 && (
        <Callout kind="caution">
          {`The draft cannot be saved until ${retired.join(", ")} ${retired.length === 1 ? "is" : "are"} removed from its criteria.`}
        </Callout>
      )}
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {settings.icp_criteria.map((criterion, index) => (
          <li key={criterion.key} className="flex items-center gap-2 rounded-control px-2.5 py-1.5">
            <span className="num w-24 shrink-0 font-medium">{criterion.key}</span>
            <span className="min-w-0 flex-1 truncate">
              {enumLabel(criterion.kind)}: {operandSummary(criterion)}
              {(criterion.values ?? []).some((value) => retired.includes(value)) && (
                <Chip tone="caution">Retired</Chip>
              )}
            </span>
            <span className="shrink-0 text-hint text-text-tertiary">
              {enumLabel(criterion.weight)}
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
              aria-label={`Remove criterion ${criterion.key}`}
              onClick={() => {
                remove(index);
              }}
            >
              <XIcon size={14} aria-hidden />
            </Button>
          </li>
        ))}
      </ul>
      {editingCriterion !== undefined && (
        <CriterionDialog
          open
          onOpenChange={(next) => {
            if (!next) {
              setEditingIndex(null);
            }
          }}
          criterion={editingCriterion}
          industries={industries}
          markets={markets}
          onSave={(criterion) => {
            save(editingIndex, criterion);
          }}
        />
      )}
      <CriterionDialog
        trigger={
          <Button type="button" variant="secondary" size="small" className="self-start">
            <PlusIcon size={14} aria-hidden />
            Add criterion
          </Button>
        }
        industries={industries}
        markets={markets}
        onSave={(criterion) => {
          save(null, criterion);
        }}
      />
      {errors["/icp_criteria"] !== undefined && (
        <span className="text-hint text-negative">{errors["/icp_criteria"]}</span>
      )}
    </div>
  );
}
