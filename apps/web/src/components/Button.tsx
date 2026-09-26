import { Link, type LinkProps } from "react-router";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";
import { Tooltip } from "./Tooltip";

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "default" | "small";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-control px-3.5 font-medium whitespace-nowrap active:translate-y-px disabled:opacity-50 disabled:pointer-events-none";

const variants: Record<ButtonVariant, string> = {
  // A primary button keeps its colour on hover (FR-124).
  primary: "bg-accent text-on-accent",
  secondary: "border border-control-border bg-surface text-text hover:bg-page",
  ghost: "text-text hover:bg-page",
};

const sizes: Record<ButtonSize, string> = {
  default: "h-control",
  small: "h-control-small",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "default", className, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(base, variants[variant], sizes[size], className)}
      {...rest}
    />
  );
});

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> {
  /** The accessible name, also the tooltip (FR-110). */
  label: string;
  icon: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "ghost", size = "default", className, type = "button", ...rest },
  ref,
) {
  return (
    <Tooltip content={label}>
      <button
        ref={ref}
        type={type}
        aria-label={label}
        className={cn(
          base,
          "px-0",
          variants[variant],
          sizes[size],
          size === "small" ? "w-control-small" : "w-control",
          className,
        )}
        {...rest}
      >
        {icon}
      </button>
    </Tooltip>
  );
});

interface ButtonLinkProps extends LinkProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

/** A link that looks like a button, for navigation such as "Back to Prospects". */
export function ButtonLink({
  variant = "secondary",
  size = "default",
  className,
  ...rest
}: ButtonLinkProps) {
  return <Link className={cn(base, variants[variant], sizes[size], className)} {...rest} />;
}
