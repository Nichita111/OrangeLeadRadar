import type { TextareaHTMLAttributes } from "react";

import { cn } from "./cn";

const control =
  "w-full rounded-control border border-control-border bg-surface px-3 py-2 text-text placeholder:text-text-tertiary disabled:opacity-60 aria-[invalid=true]:border-negative";

/** The multi-line sibling of [`Input`](./controls.tsx), the same field layout (FR-119) through
 * [`FormField`](./FormField.tsx). */
export function Textarea({
  className,
  rows = 3,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} className={cn(control, className)} {...rest} />;
}
