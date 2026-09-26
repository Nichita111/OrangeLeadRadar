/**
 * The role and status pickers of the [Users](/features/identity-and-access.md#users) screen, on
 * the Radix Select primitive for keyboard and screen-reader behaviour
 * ([TypeScript guidelines](/guidelines/typescript.md#styling-and-accessibility)). Same field
 * layout as [`Input`](./Input.tsx) (`FR-119`).
 */
import { CheckIcon, CaretDownIcon } from "@phosphor-icons/react";
import * as RadixSelect from "@radix-ui/react-select";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  id: string;
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  hint?: string | undefined;
  error?: string | undefined;
  disabled?: boolean | undefined;
}

export function Select({
  id,
  label,
  value,
  onValueChange,
  options,
  hint,
  error,
  disabled,
}: SelectProps) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text">
        {label}
      </label>
      <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled ?? false}>
        <RadixSelect.Trigger
          id={id}
          aria-describedby={describedBy.length > 0 ? describedBy : undefined}
          className={`flex items-center justify-between gap-2 rounded-control border bg-surface px-3 text-sm text-text data-[placeholder]:text-text-tertiary disabled:opacity-50 ${
            error !== undefined ? "border-negative" : "border-border"
          }`}
          style={{ height: "var(--ctl-input)" }}
        >
          <RadixSelect.Value />
          <RadixSelect.Icon>
            <CaretDownIcon size={16} />
          </RadixSelect.Icon>
        </RadixSelect.Trigger>
        <RadixSelect.Portal>
          <RadixSelect.Content
            position="popper"
            sideOffset={4}
            className="overflow-hidden rounded-control border border-border bg-surface shadow-lg"
          >
            <RadixSelect.Viewport className="p-1">
              {options.map((option) => (
                <RadixSelect.Item
                  key={option.value}
                  value={option.value}
                  className="flex cursor-pointer items-center justify-between gap-2 rounded-control px-3 py-2 text-sm text-text outline-none data-[highlighted]:bg-page"
                >
                  <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
                  <RadixSelect.ItemIndicator>
                    <CheckIcon size={16} />
                  </RadixSelect.ItemIndicator>
                </RadixSelect.Item>
              ))}
            </RadixSelect.Viewport>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
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
