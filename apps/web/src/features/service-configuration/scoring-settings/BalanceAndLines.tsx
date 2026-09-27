import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";
import { fitShareChoices } from "./scoringDraft";

type ScoringSettings = Schemas["ScoringSettings"];

interface BalanceAndLinesProps {
  settings: ScoringSettings;
  onChange: (next: ScoringSettings) => void;
  errors: Partial<Record<string, string>>;
}

/** FR-029, FR-151 (G3): Balance sets `fit_weight`/`intent_weight`; Lines sets the three
 * thresholds. */
export function BalanceAndLines({ settings, onChange, errors }: BalanceAndLinesProps) {
  const selectedPercent = Math.round(settings.fit_weight * 100);
  const choices = fitShareChoices(settings.fit_weight);

  function setFitPercent(percent: number) {
    const fit_weight = percent / 100;
    onChange({ ...settings, fit_weight, intent_weight: Math.round((1 - fit_weight) * 100) / 100 });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <span className="font-medium">Fit share</span>
        <div role="group" aria-label="Fit share" className="flex gap-1">
          {choices.map((percent) => (
            <Button
              key={percent}
              type="button"
              size="small"
              variant={percent === selectedPercent ? "primary" : "secondary"}
              aria-pressed={percent === selectedPercent}
              onClick={() => {
                setFitPercent(percent);
              }}
            >
              {`${String(percent)}%`}
            </Button>
          ))}
        </div>
        <span className="text-hint text-text-secondary">
          {`Intent share ${String(Math.round(settings.intent_weight * 100))}%`}
        </span>
        {errors["/intent_weight"] !== undefined && (
          <span className="text-hint text-negative">{errors["/intent_weight"]}</span>
        )}
      </div>
      <div className="flex gap-4">
        <FormField label="Minimum fit" error={errors["/min_fit"]}>
          {(field) => (
            <Input
              {...field}
              type="number"
              value={settings.min_fit}
              onChange={(event) => {
                onChange({ ...settings, min_fit: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
        <FormField label="Warm from" error={errors["/warm_threshold"]}>
          {(field) => (
            <Input
              {...field}
              type="number"
              value={settings.warm_threshold}
              onChange={(event) => {
                onChange({ ...settings, warm_threshold: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
        <FormField label="Hot from" error={errors["/hot_threshold"]}>
          {(field) => (
            <Input
              {...field}
              type="number"
              value={settings.hot_threshold}
              onChange={(event) => {
                onChange({ ...settings, hot_threshold: Number(event.target.value) });
              }}
            />
          )}
        </FormField>
      </div>
    </div>
  );
}
