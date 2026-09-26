/**
 * An on/off switch, full radius per [Visual language]
 * (/architecture/services/frontend.md#visual-language). A native checkbox styled as a switch, so
 * it is reachable and operable by keyboard without extra ARIA plumbing (`FR-016`); the label is
 * always shown beside it, never colour alone.
 */
export interface SwitchProps {
  id: string;
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function Switch({ id, label, checked, onCheckedChange, disabled = false }: SwitchProps) {
  return (
    <label htmlFor={id} className="inline-flex items-center gap-2 text-sm text-text">
      <span className="relative inline-flex h-5 w-9 shrink-0 items-center">
        <input
          id={id}
          type="checkbox"
          role="switch"
          aria-checked={checked}
          checked={checked}
          disabled={disabled}
          onChange={(event) => {
            onCheckedChange(event.target.checked);
          }}
          className="sr-only"
        />
        <span
          aria-hidden="true"
          className={`h-5 w-9 rounded-full transition-colors ${
            checked ? "bg-accent" : "bg-border"
          } ${disabled ? "opacity-50" : ""}`}
        >
          <span
            className={`block h-4 w-4 translate-y-0.5 rounded-full bg-surface transition-transform ${
              checked ? "translate-x-[18px]" : "translate-x-0.5"
            }`}
          />
        </span>
      </span>
      {label}
    </label>
  );
}
