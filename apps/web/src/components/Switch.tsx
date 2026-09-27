import { cn } from "./cn";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** The accessible name. */
  label: string;
  disabled?: boolean;
}

/**
 * A native `role="switch"` button (Visual language switch radius: full). No Radix dependency: a
 * native button already toggles on both Enter and Space (`FR-016`).
 */
export function Switch({ checked, onChange, label, disabled = false }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => {
        onChange(!checked);
      }}
      className={cn(
        "relative h-5 w-9 shrink-0 rounded-full disabled:opacity-50 disabled:pointer-events-none",
        checked ? "bg-accent" : "bg-control-border",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute top-0.5 block h-4 w-4 rounded-full bg-surface",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
