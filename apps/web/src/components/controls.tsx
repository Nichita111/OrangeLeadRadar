import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";

import { cn } from "./cn";

const control =
  "w-full rounded-control border border-control-border bg-surface px-3 text-text placeholder:text-text-tertiary disabled:opacity-60 aria-[invalid=true]:border-negative";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(control, "h-control-input", className)} {...rest} />;
}

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(control, "h-control-input", className)} {...rest} />;
}
