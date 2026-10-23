import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, CSSProperties } from "react";

/**
 * The one button. `primary` is dark ink on the cyan accent (the pairing
 * ErrorState, Account, Premium, SignIn, AgeGate and Onboarding already used);
 * `secondary` is a quiet outlined button; `ghost` is a text-style action.
 * A disabled primary falls back to the muted surface so it never reads as
 * live. Never put white text on the cyan accent.
 */
export type ButtonVariant = "primary" | "secondary" | "ghost";

type ButtonLook = { variant?: ButtonVariant; size?: "sm" | "md"; fullWidth?: boolean };

function buttonLook(
  { variant = "primary", size = "md", fullWidth = false }: ButtonLook,
  disabled: boolean,
  className: string,
  style?: CSSProperties,
) {
  const palette =
    variant === "primary"
      ? {
          background: disabled ? "var(--color-surface-muted)" : "var(--color-accent-strong)",
          color: disabled ? "var(--color-text-muted)" : "var(--color-on-accent)",
        }
      : variant === "secondary"
        ? {
            background: "transparent",
            color: disabled ? "var(--color-text-muted)" : "var(--color-text-primary)",
            border: "var(--border-width-default) solid var(--color-border-strong)",
          }
        : { background: "transparent", color: disabled ? "var(--color-text-muted)" : "var(--color-accent)" };
  return {
    className: `${size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm"} min-h-[var(--touch-target-min)] inline-flex items-center justify-center font-bold ${fullWidth ? "w-full" : "self-start"} ${className}`.trim(),
    style: {
      ...palette,
      fontWeight: "var(--font-weight-button)",
      borderRadius: "var(--radius-control)",
      cursor: disabled ? "not-allowed" : "pointer",
      ...style,
    } as CSSProperties,
  };
}

export function Button({
  variant,
  size,
  fullWidth,
  className = "",
  style,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & ButtonLook) {
  const look = buttonLook({ variant, size, fullWidth }, Boolean(rest.disabled), className, style);
  return <button type={type} {...look} {...rest} />;
}

/** The same button as a navigation link (next/link). */
export function ButtonLink({
  variant,
  size,
  fullWidth,
  className = "",
  style,
  href,
  ...rest
}: Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & ButtonLook & { href: string }) {
  const look = buttonLook({ variant, size, fullWidth }, false, className, style);
  return <Link href={href} {...look} {...rest} />;
}
