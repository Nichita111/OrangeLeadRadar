/**
 * The one filled button of a page header is `variant="primary"`; every other action is
 * `secondary` or `ghost`, per [Page anatomy](/architecture/services/frontend.md#page-anatomy)
 * (`FR-104`). Control height comes from the [Visual language]
 * (/architecture/services/frontend.md#visual-language) token, never a literal.
 */
import { forwardRef, type ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "default" | "small";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-accent text-on-accent hover:opacity-90",
  secondary: "border border-border bg-surface text-text hover:bg-page",
  ghost: "bg-transparent text-text hover:bg-page",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "default", className = "", style, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control px-4 text-sm font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`}
      style={{ height: size === "small" ? "var(--ctl-small)" : "var(--ctl-button)", ...style }}
      {...props}
    />
  );
});
