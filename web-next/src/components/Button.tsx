import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, CSSProperties } from "react";

/**
 * The one button. `primary` is dark ink on the cyan accent (the pairing
 * ErrorState, Account, Premium, SignIn, AgeGate and Onboarding already used);
 * `secondary` is a quiet outlined button; `ghost` is a text-style action;
 * `danger` / `dangerOutline` are the destructive fill and outline. `loading`
 * marks an in-flight action (disabled, aria-busy, spinner before the label).
 * A disabled primary falls back to the muted surface so it never reads as
 * live. Never put white text on the cyan accent. `premium` is the gold fill
 * with dark ink and a soft pulsing gold glow (the prestige-ring recipe) for
 * EVERY premium-related control (Upgrade, trial CTAs, Manage Billing);
 * `premiumOutline` is its quiet gold-outline sibling (Restore purchases).
 */
export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "dangerOutline" | "premium" | "premiumOutline";

type ButtonLook = { variant?: ButtonVariant; size?: "sm" | "md"; fullWidth?: boolean };

function palette(variant: ButtonVariant, disabled: boolean): CSSProperties {
  const muted = "var(--color-text-muted)";
  switch (variant) {
    case "primary":
      return {
        background: disabled ? "var(--color-surface-muted)" : "var(--color-accent-strong)",
        color: disabled ? muted : "var(--color-on-accent)",
      };
    case "premium":
      return {
        background: disabled ? "var(--color-surface-muted)" : "var(--color-premium-fill)",
        color: disabled ? muted : "var(--color-on-premium)",
      };
    case "premiumOutline":
      return {
        background: "transparent",
        color: disabled ? muted : "var(--color-premium)",
        border: `var(--border-width-default) solid ${disabled ? "var(--color-border-strong)" : "var(--color-premium)"}`,
      };
    case "danger":
      return {
        background: disabled ? "var(--color-surface-muted)" : "var(--color-danger)",
        color: disabled ? muted : "var(--color-on-accent)",
      };
    case "dangerOutline":
      return {
        background: "transparent",
        color: disabled ? muted : "var(--color-danger)",
        border: `var(--border-width-default) solid ${disabled ? "var(--color-border-strong)" : "var(--color-danger)"}`,
      };
    case "secondary":
      return {
        background: "transparent",
        color: disabled ? muted : "var(--color-text-primary)",
        border: "var(--border-width-default) solid var(--color-border-strong)",
      };
    default:
      return { background: "transparent", color: disabled ? muted : "var(--color-accent)" };
  }
}

function buttonLook(
  { variant = "primary", size = "md", fullWidth = false }: ButtonLook,
  disabled: boolean,
  className: string,
  style?: CSSProperties,
) {
  return {
    className: `${size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm"} min-h-[var(--touch-target-min)] inline-flex items-center justify-center font-bold ${fullWidth ? "w-full" : "self-start"} ${variant === "premium" ? "premium-glow" : ""} ${className}`.trim(),
    style: {
      ...palette(variant, disabled),
      fontWeight: "var(--font-weight-button)",
      borderRadius: "var(--radius-control)",
      cursor: disabled ? "not-allowed" : "pointer",
      ...style,
    } as CSSProperties,
  };
}

/** Small ring spinner shown inside a `loading` button (the label stays). */
function ButtonSpinner() {
  return (
    <span
      aria-hidden="true"
      className="mr-2 inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}

export function Button({
  variant,
  size,
  fullWidth,
  loading = false,
  className = "",
  style,
  type = "button",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & ButtonLook & { loading?: boolean }) {
  const look = buttonLook({ variant, size, fullWidth }, Boolean(rest.disabled), className, style);
  return (
    <button
      type={type}
      {...look}
      {...rest}
      disabled={Boolean(rest.disabled) || loading}
      aria-busy={loading || undefined}
      style={loading ? { ...look.style, opacity: "var(--opacity-disabled)", cursor: "progress" } : look.style}
    >
      {loading ? <ButtonSpinner /> : null}
      {children}
    </button>
  );
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
