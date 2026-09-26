/**
 * A multi-select of checkboxes, same field layout as [`Input`](./Input.tsx) (`FR-119`). `searchable`
 * adds a filter box above a scrollable list, for a long option set such as countries (`FR-155`);
 * without it every option is shown inline, for a short set such as source types.
 */
import { useId, useState } from "react";

export interface CheckboxGroupOption {
  value: string;
  label: string;
}

export interface CheckboxGroupProps {
  id: string;
  label: string;
  options: CheckboxGroupOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  hint?: string | undefined;
  error?: string | undefined;
  searchable?: boolean;
}

export function CheckboxGroup({
  id,
  label,
  options,
  selected,
  onChange,
  hint,
  error,
  searchable = false,
}: CheckboxGroupProps) {
  const [filter, setFilter] = useState("");
  const filterId = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  const visible =
    searchable && filter.trim().length > 0
      ? options.filter((option) => option.label.toLowerCase().includes(filter.toLowerCase()))
      : options;

  const toggle = (value: string) => {
    onChange(
      selected.includes(value) ? selected.filter((entry) => entry !== value) : [...selected, value],
    );
  };

  return (
    <div className="flex flex-col gap-1.5">
      <span id={id} className="text-sm font-medium text-text">
        {label}
      </span>
      {searchable && (
        <input
          id={filterId}
          type="text"
          placeholder="Filter…"
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value);
          }}
          className="rounded-control border border-border bg-surface px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none"
          style={{ height: "var(--ctl-input)" }}
          aria-label={`Filter ${label.toLowerCase()}`}
        />
      )}
      <div
        role="group"
        aria-labelledby={id}
        aria-describedby={describedBy.length > 0 ? describedBy : undefined}
        className={`flex flex-wrap gap-x-4 gap-y-2 rounded-control border p-3 ${
          searchable ? "max-h-48 overflow-y-auto" : ""
        } ${error !== undefined ? "border-negative" : "border-border"}`}
      >
        {visible.length === 0 && <p className="text-sm text-text-tertiary">No matches.</p>}
        {visible.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm text-text">
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
        <p id={hintId} className="text-[12.5px] leading-snug text-text-tertiary">
          {hint}
        </p>
      )}
      {error !== undefined && (
        <p id={errorId} role="alert" className="text-[12.5px] leading-snug text-negative">
          {error}
        </p>
      )}
    </div>
  );
}
