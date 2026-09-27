import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState, type ReactElement } from "react";

import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { CheckboxGroup } from "../../../components/CheckboxGroup";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Input, Select } from "../../../components/controls";
import { COUNTRY_CODES } from "../../../shell/countries";
import { enumLabel, countryName } from "../../../shell/format";
import { toUpperSnakeInput } from "../../../shell/upperSnake";
import { addMarketCountries } from "./scoringDraft";

type ICPCriterion = Schemas["ICPCriterion"];
type ICPCriterionKind = Schemas["ICPCriterionKind"];

const KINDS: ICPCriterionKind[] = [
  "INDUSTRY",
  "GEOGRAPHY",
  "EMPLOYEE_RANGE",
  "REVENUE_RANGE",
  "OPERATIONAL_COMPLEXITY",
];
const WEIGHTS: Schemas["WeightLevel"][] = ["HIGH", "MEDIUM", "LOW", "NONE"];
const COMPLEXITY_LEVELS: Schemas["AccountOperationalComplexity"][] = ["LOW", "MEDIUM", "HIGH"];
const COUNTRY_OPTIONS = COUNTRY_CODES.map((code) => ({
  value: code,
  label: `${countryName(code)} (${code})`,
}));

function isListKind(kind: ICPCriterionKind): boolean {
  return kind === "INDUSTRY" || kind === "GEOGRAPHY" || kind === "OPERATIONAL_COMPLEXITY";
}

interface CriterionDialogProps {
  trigger?: ReactElement;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  criterion?: ICPCriterion;
  industries: Schemas["Industry"][];
  markets: Schemas["Market"][];
  onSave: (criterion: ICPCriterion) => void;
}

/** FR-030: adds or edits one ICP criterion; a market shortcut expands to its country codes. */
export function CriterionDialog({
  trigger,
  open,
  onOpenChange,
  criterion,
  industries,
  markets,
  onSave,
}: CriterionDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const currentOpen = open ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;
  const editing = criterion !== undefined;

  const [key, setKey] = useState(criterion?.key ?? "");
  const [kind, setKind] = useState<ICPCriterionKind>(criterion?.kind ?? "INDUSTRY");
  const [values, setValues] = useState<string[]>(criterion?.values ?? []);
  const [min, setMin] = useState<number | null>(criterion?.min ?? null);
  const [max, setMax] = useState<number | null>(criterion?.max ?? null);
  const [weight, setWeight] = useState<Schemas["WeightLevel"]>(criterion?.weight ?? "MEDIUM");

  function submit() {
    onSave({
      key,
      kind,
      weight,
      ...(isListKind(kind) ? { values } : {}),
      ...(kind === "EMPLOYEE_RANGE" || kind === "REVENUE_RANGE"
        ? { min: min ?? 0, ...(max !== null && { max }) }
        : {}),
    });
    setOpen(false);
  }

  const listOptions =
    kind === "INDUSTRY"
      ? industries
          .filter((industry) => industry.status === "ACTIVE")
          .map((industry) => ({ value: industry.code, label: industry.label }))
      : kind === "OPERATIONAL_COMPLEXITY"
        ? COMPLEXITY_LEVELS.map((level) => ({ value: level, label: enumLabel(level) }))
        : COUNTRY_OPTIONS;

  return (
    <Dialog
      {...(trigger === undefined ? {} : { trigger })}
      title={editing ? "Edit criterion" : "New criterion"}
      description="Sets the weight of one part of your ideal customer profile."
      open={currentOpen}
      onOpenChange={setOpen}
    >
      <div className="flex flex-col gap-4">
        <FormField label="Key">
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
        <FormField label="Kind">
          {(field) => (
            <Select
              {...field}
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as ICPCriterionKind);
                setValues([]);
              }}
            >
              {KINDS.map((option) => (
                <option key={option} value={option}>
                  {enumLabel(option)}
                </option>
              ))}
            </Select>
          )}
        </FormField>
        {isListKind(kind) ? (
          <>
            {kind === "GEOGRAPHY" && markets.length > 0 && (
              <FormField label="Add a market's countries">
                {(field) => (
                  <Select
                    {...field}
                    value=""
                    onChange={(event) => {
                      const market = markets.find((entry) => entry.code === event.target.value);
                      if (market !== undefined) {
                        setValues(addMarketCountries(values, market));
                      }
                    }}
                  >
                    <option value="">Choose a market…</option>
                    {markets
                      .filter((market) => market.status === "ACTIVE")
                      .map((market) => (
                        <option key={market.code} value={market.code}>
                          {market.name}
                        </option>
                      ))}
                  </Select>
                )}
              </FormField>
            )}
            <CheckboxGroup
              label={
                kind === "INDUSTRY" ? "Industries" : kind === "GEOGRAPHY" ? "Countries" : "Levels"
              }
              options={listOptions}
              selected={values}
              onChange={setValues}
            />
          </>
        ) : (
          <div className="flex gap-4">
            <FormField label="Minimum">
              {(field) => (
                <Input
                  {...field}
                  type="number"
                  value={min ?? ""}
                  onChange={(event) => {
                    setMin(event.target.value === "" ? null : Number(event.target.value));
                  }}
                />
              )}
            </FormField>
            <FormField label="Maximum" hint="Leave empty for no upper bound.">
              {(field) => (
                <Input
                  {...field}
                  type="number"
                  value={max ?? ""}
                  onChange={(event) => {
                    setMax(event.target.value === "" ? null : Number(event.target.value));
                  }}
                />
              )}
            </FormField>
          </div>
        )}
        <FormField label="Weight">
          {(field) => (
            <Select
              {...field}
              value={weight}
              onChange={(event) => {
                setWeight(event.target.value as Schemas["WeightLevel"]);
              }}
            >
              {WEIGHTS.map((option) => (
                <option key={option} value={option}>
                  {enumLabel(option)}
                </option>
              ))}
            </Select>
          )}
        </FormField>
        <div className="flex justify-end gap-2">
          <DialogPrimitive.Close asChild>
            <Button type="button" variant="secondary">
              Cancel
            </Button>
          </DialogPrimitive.Close>
          <Button type="button" variant="primary" onClick={submit}>
            Save
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
