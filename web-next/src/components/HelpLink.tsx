import { HELP_LINK_LABEL, supportMailto, type SupportContext } from "@/lib/support";

/**
 * The one help / feedback entry (mailto, prefilled with where the user was).
 * Placed on connect errors, error states, Account and the paywall.
 * Mirrors mobile/src/components/HelpLink.tsx.
 */
export function HelpLink({
  context,
  label = HELP_LINK_LABEL,
  className,
}: {
  context?: SupportContext;
  label?: string;
  className?: string;
}) {
  return (
    <a
      href={supportMailto(context, "web")}
      className={`tap-link text-xs underline ${className ?? ""}`}
      style={{ color: "var(--color-text-muted)" }}
      data-testid="help-link"
    >
      {label}
    </a>
  );
}
