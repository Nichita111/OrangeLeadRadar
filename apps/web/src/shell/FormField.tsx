import { useId, type ReactElement, type ReactNode } from "react";

/**
 * `FR-119`: label above, hint below the label, error below the input in words, wired through
 * `aria-describedby`. `FR-007`: the caller keeps the user's input on a failed save and passes
 * the [field error](../api/errors.ts) here; a placeholder is never the label.
 */
export function FormField({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: (inputProps: { id: string; "aria-describedby": string | undefined }) => ReactNode;
}): ReactElement {
  const id = useId();
  const hintId = hint !== undefined ? `${id}-hint` : undefined;
  const errorId = error !== undefined ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter((value) => value !== undefined).join(" ");

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-text">
        {label}
      </label>
      {hint !== undefined ? (
        <p id={hintId} className="text-hint text-text-tertiary">
          {hint}
        </p>
      ) : null}
      {children({ id, "aria-describedby": describedBy === "" ? undefined : describedBy })}
      {error !== undefined ? (
        <p id={errorId} className="text-sm text-negative">
          {error}
        </p>
      ) : null}
    </div>
  );
}
