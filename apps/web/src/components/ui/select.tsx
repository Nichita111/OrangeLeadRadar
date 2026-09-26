import * as RadixSelect from "@radix-ui/react-select";
import { CaretDownIcon, CheckIcon } from "@phosphor-icons/react";
import type { ReactElement } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

/** [Visual language](/architecture/services/frontend.md#visual-language): 38 px control height,
 * Control border token, visible focus ring. */
export function Select({
  value,
  onValueChange,
  options,
  ariaLabel,
}: {
  value: string | undefined;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  ariaLabel: string;
}): ReactElement {
  return (
    <RadixSelect.Root {...(value === undefined ? {} : { value })} onValueChange={onValueChange}>
      <RadixSelect.Trigger
        aria-label={ariaLabel}
        className="inline-flex h-control-input items-center gap-2 rounded-control border border-control-border bg-surface px-3 text-sm text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <RadixSelect.Value />
        <RadixSelect.Icon>
          <CaretDownIcon size={16} />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content className="rounded-control border border-border bg-surface shadow-md">
          <RadixSelect.Viewport>
            {options.map((option) => (
              <RadixSelect.Item
                key={option.value}
                value={option.value}
                className="flex items-center gap-2 px-3 py-2 text-sm text-text data-[highlighted]:bg-accent-soft data-[highlighted]:outline-none"
              >
                <RadixSelect.ItemIndicator>
                  <CheckIcon size={14} />
                </RadixSelect.ItemIndicator>
                <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
