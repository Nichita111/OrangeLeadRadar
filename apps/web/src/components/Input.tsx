/**
 * `FR-119`: label above the input, hint below the label or the input, error below the input in
 * words; a placeholder is never the label.
 */
import { forwardRef, type InputHTMLAttributes } from "react";

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  id: string;
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { id, label, hint, error, className = "", ...props },
  ref,
) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text">
        {label}
      </label>
      <input
        ref={ref}
        id={id}
        aria-invalid={error !== undefined}
        aria-describedby={describedBy.length > 0 ? describedBy : undefined}
        className={`rounded-control border bg-surface px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none disabled:opacity-50 ${
          error !== undefined ? "border-negative" : "border-border"
        } ${className}`}
        style={{ height: "var(--ctl-input)" }}
        {...props}
      />
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
});
