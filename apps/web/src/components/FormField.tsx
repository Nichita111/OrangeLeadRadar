import { useId, type ReactNode } from "react";

interface FieldProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

interface FormFieldProps {
  label: string;
  hint?: string;
  error?: string | undefined;
  children: (field: FieldProps) => ReactNode;
}

/** FR-119: label above, hint and error below the input, linked by `aria-describedby`. */
export function FormField({ label, hint, error, children }: FormFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint !== undefined && hintId, error !== undefined && errorId]
    .filter((part): part is string => part !== false)
    .join(" ");
  const field: FieldProps = { id };
  if (describedBy !== "") {
    field["aria-describedby"] = describedBy;
  }
  if (error !== undefined) {
    field["aria-invalid"] = true;
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      {children(field)}
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
