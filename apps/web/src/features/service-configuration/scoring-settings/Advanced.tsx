import { useState } from "react";

import type { Schemas } from "../../../api/contract";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";

type ScoringSettings = Schemas["ScoringSettings"];

const WEIGHT_LEVELS = ["HIGH", "MEDIUM", "LOW", "NONE"] as const;
const STRENGTHS = ["WEAK", "MEDIUM", "STRONG"] as const;
const SOURCE_TYPES = ["NEWS", "COMPANY_PUBLICATION", "JOB_POSTING", "COMPANY_PROFILE"] as const;

interface AdvancedProps {
  settings: ScoringSettings;
  onChange: (next: ScoringSettings) => void;
  errors: Partial<Record<string, string>>;
  /** Opens the section by itself when an error lands inside it. */
  hasError: boolean;
}

/** FR-033: `weight_values`, `strength_values`, `default_half_life_days`, `min_decay`,
 * `negative_factor`, `intent_saturation` and `unknown_match`, collapsed by default. */
export function Advanced({ settings, onChange, errors, hasError }: AdvancedProps) {
  const [openedByUser, setOpenedByUser] = useState(false);

  function setWeightValue(level: string, value: number) {
    onChange({ ...settings, weight_values: { ...settings.weight_values, [level]: value } });
  }
  function setStrengthValue(level: string, value: number) {
    onChange({ ...settings, strength_values: { ...settings.strength_values, [level]: value } });
  }
  function setHalfLife(sourceType: string, value: number) {
    onChange({
      ...settings,
      default_half_life_days: { ...settings.default_half_life_days, [sourceType]: value },
    });
  }

  return (
    <details open={hasError || openedByUser}>
      <summary
        className="cursor-pointer font-medium"
        onClick={() => {
          setOpenedByUser(!openedByUser);
        }}
      >
        Advanced
      </summary>
      <div className="flex flex-col gap-4 pt-3">
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="p-0 font-medium">Weight values</legend>
          <p className="m-0 text-hint text-text-secondary">
            The numeric weight each level of a criterion or signal contributes to Fit or Intent.
          </p>
          <div className="flex gap-3">
            {WEIGHT_LEVELS.map((level) => (
              <FormField key={level} label={level}>
                {(field) => (
                  <Input
                    {...field}
                    type="number"
                    value={settings.weight_values[level] ?? 0}
                    onChange={(event) => {
                      setWeightValue(level, Number(event.target.value));
                    }}
                  />
                )}
              </FormField>
            ))}
          </div>
          {errors["/weight_values"] !== undefined && (
            <span className="text-hint text-negative">{errors["/weight_values"]}</span>
          )}
        </fieldset>
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="p-0 font-medium">Strength values</legend>
          <p className="m-0 text-hint text-text-secondary">
            How much of a signal's weight a finding of each strength contributes.
          </p>
          <div className="flex gap-3">
            {STRENGTHS.map((level) => (
              <FormField key={level} label={level}>
                {(field) => (
                  <Input
                    {...field}
                    type="number"
                    step="0.01"
                    value={settings.strength_values[level] ?? 0}
                    onChange={(event) => {
                      setStrengthValue(level, Number(event.target.value));
                    }}
                  />
                )}
              </FormField>
            ))}
          </div>
          {errors["/strength_values"] !== undefined && (
            <span className="text-hint text-negative">{errors["/strength_values"]}</span>
          )}
        </fieldset>
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="p-0 font-medium">Default half-life days</legend>
          <p className="m-0 text-hint text-text-secondary">
            Days for a finding's weight to halve, by source type, when the question sets none.
          </p>
          <div className="flex gap-3">
            {SOURCE_TYPES.map((sourceType) => (
              <FormField key={sourceType} label={sourceType}>
                {(field) => (
                  <Input
                    {...field}
                    type="number"
                    value={settings.default_half_life_days[sourceType] ?? 0}
                    onChange={(event) => {
                      setHalfLife(sourceType, Number(event.target.value));
                    }}
                  />
                )}
              </FormField>
            ))}
          </div>
          {errors["/default_half_life_days"] !== undefined && (
            <span className="text-hint text-negative">{errors["/default_half_life_days"]}</span>
          )}
        </fieldset>
        <FormField
          label="Minimum decay"
          hint="A finding's decay below this floor counts as zero."
          error={errors["/min_decay"]}
        >
          {(field) => (
            <Input
              {...field}
              type="number"
              step="0.01"
              value={settings.min_decay}
              onChange={(event) => {
                onChange({ ...settings, min_decay: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
        <FormField
          label="Negative factor"
          hint="How much a negative-polarity signal subtracts from Intent."
          error={errors["/negative_factor"]}
        >
          {(field) => (
            <Input
              {...field}
              type="number"
              step="0.01"
              value={settings.negative_factor}
              onChange={(event) => {
                onChange({ ...settings, negative_factor: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
        <FormField
          label="Intent saturation"
          hint="The Intent value above which further signal adds less."
          error={errors["/intent_saturation"]}
        >
          {(field) => (
            <Input
              {...field}
              type="number"
              step="0.01"
              value={settings.intent_saturation}
              onChange={(event) => {
                onChange({ ...settings, intent_saturation: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
        <FormField
          label="Unknown match"
          hint="The Fit contribution of a criterion the account has no data for."
          error={errors["/unknown_match"]}
        >
          {(field) => (
            <Input
              {...field}
              type="number"
              step="0.01"
              value={settings.unknown_match}
              onChange={(event) => {
                onChange({ ...settings, unknown_match: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
      </div>
    </details>
  );
}
