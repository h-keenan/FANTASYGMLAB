import type { ButtonHTMLAttributes } from "react";

/**
 * The one button. `primary` is dark ink on the cyan accent (the pairing
 * ErrorState, Account, Premium, SignIn, AgeGate and Onboarding already used);
 * `secondary` is a quiet outlined button; `ghost` is a text-style action.
 * A disabled primary falls back to the muted surface so it never reads as
 * live. Never put white text on the cyan accent.
 */
export type ButtonVariant = "primary" | "secondary" | "ghost";

export function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  style,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  fullWidth?: boolean;
}) {
  const disabled = Boolean(rest.disabled);
  const palette =
    variant === "primary"
      ? {
          background: disabled ? "var(--color-surface-muted)" : "var(--color-accent-strong)",
          color: disabled ? "var(--color-text-muted)" : "var(--color-brand-mark-ink)",
        }
      : variant === "secondary"
        ? {
            background: "transparent",
            color: disabled ? "var(--color-text-muted)" : "var(--color-text-primary)",
            border: "var(--border-width-default) solid var(--color-border-strong)",
          }
        : { background: "transparent", color: disabled ? "var(--color-text-muted)" : "var(--color-accent)" };
  return (
    <button
      type={type}
      className={`${size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm"} font-bold ${fullWidth ? "w-full" : "self-start"} ${className}`.trim()}
      style={{
        ...palette,
        fontWeight: "var(--font-weight-button)",
        borderRadius: "var(--radius-control)",
        cursor: disabled ? "not-allowed" : "pointer",
        ...style,
      }}
      {...rest}
    />
  );
}
