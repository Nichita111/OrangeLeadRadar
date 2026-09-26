/**
 * The multi-line sibling of [`Input`](./Input.tsx), same field layout (`FR-119`): label above,
 * hint below the label or the field, error below the field in words.
 */
import { forwardRef, type TextareaHTMLAttributes } from "react";

export interface TextareaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {
  id: string;
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { id, label, hint, error, className = "", rows = 3, ...props },
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
      <textarea
        ref={ref}
        id={id}
        rows={rows}
        aria-invalid={error !== undefined}
        aria-describedby={describedBy.length > 0 ? describedBy : undefined}
        className={`rounded-control border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none disabled:opacity-50 ${
          error !== undefined ? "border-negative" : "border-border"
        } ${className}`}
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
