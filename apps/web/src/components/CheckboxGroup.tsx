import { useId } from "react";

export interface CheckboxGroupOption {
  value: string;
  label: string;
}

interface CheckboxGroupProps {
  label: string;
  options: CheckboxGroupOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  hint?: string | undefined;
  error?: string | undefined;
}

/**
 * A multi-select of checkboxes, the field layout of [`FormField`](./FormField.tsx) (label above,
 * hint and error below) without a single input `FormField` can wrap, since the field is a group
 * (`FR-119`).
 */
export function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
  hint,
  error,
}: CheckboxGroupProps) {
  const id = useId();
  const labelId = `${id}-label`;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint !== undefined && hintId, error !== undefined && errorId]
    .filter((part): part is string => part !== false)
    .join(" ");

  function toggle(value: string) {
    onChange(
      selected.includes(value) ? selected.filter((entry) => entry !== value) : [...selected, value],
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span id={labelId} className="font-medium">
        {label}
      </span>
      <div
        role="group"
        aria-labelledby={labelId}
        {...(describedBy !== "" ? { "aria-describedby": describedBy } : {})}
        className={`flex max-h-64 flex-wrap gap-x-4 gap-y-2 overflow-y-auto rounded-control border p-3 ${error !== undefined ? "border-negative" : "border-control-border"}`}
      >
        {options.map((option) => (
          <label key={option.value} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selected.includes(option.value)}
              onChange={() => {
                toggle(option.value);
              }}
            />
            {option.label}
          </label>
        ))}
      </div>
      {hint !== undefined && (
        <span id={hintId} className="text-hint text-text-tertiary">
          {hint}
        </span>
      )}
      {error !== undefined && (
        <span id={errorId} className="text-hint text-negative">
          {error}
        </span>
      )}
    </div>
  );
}
