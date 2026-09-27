import { DotsThreeVerticalIcon } from "@phosphor-icons/react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";

export interface RowMenuItem {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
}

interface RowMenuProps {
  /** The accessible name of the trigger, e.g. "Actions for Intelligent Automation". */
  label: string;
  items: RowMenuItem[];
}

/**
 * A row's overflow menu, on `@radix-ui/react-dropdown-menu` (`FR-020`, `FR-156`): no existing
 * primitive is an accessible menu of several row actions.
 */
export function RowMenu({ label, items }: RowMenuProps): ReactNode {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={label}
          className="inline-flex h-control-small w-control-small items-center justify-center rounded-control text-text hover:bg-page"
        >
          <DotsThreeVerticalIcon size={16} aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-50 flex min-w-40 flex-col gap-0.5 rounded-control border border-border bg-surface p-1 shadow-overlay"
        >
          {items.map((item) => (
            <DropdownMenu.Item
              key={item.label}
              disabled={item.disabled}
              onSelect={item.onSelect}
              className="cursor-pointer rounded-control px-2.5 py-1.5 text-left outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-page"
            >
              {item.label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
