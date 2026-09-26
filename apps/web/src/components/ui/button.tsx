import { Slot } from "@radix-ui/react-slot";
import { forwardRef, type ButtonHTMLAttributes } from "react";

/**
 * [Visual language](/architecture/services/frontend.md#visual-language): control height 36 px,
 * radius 10 px, a visible focus ring ([FR-016](/architecture/services/frontend.md#accessibility)).
 * `FR-104`: at most one primary (filled) button outside a dialog; every other action is
 * secondary or ghost.
 */
export type ButtonVariant = "primary" | "secondary" | "ghost";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-accent text-on-accent hover:opacity-90",
  secondary: "border border-control-border text-text hover:bg-surface",
  ghost: "text-text hover:bg-surface",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", asChild = false, className = "", ...props },
  ref,
) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      ref={ref}
      className={`inline-flex h-control-button items-center justify-center rounded-control px-4 text-sm font-medium transition-opacity focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
});
