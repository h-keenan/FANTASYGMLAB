/**
 * The one status pill: a small uppercase rounded pill tinted from one
 * semantic color (15% fill of the same color as the text). Owner decision
 * (docs/ui-module-inventory.md B9): rounded pill everywhere. Position badges
 * share the pill shape but keep their own per-position tint in
 * `PositionBadge`; `PlayerInjuryBadge` is this pill at `size="xs"`.
 *
 * `color` is a CSS color expression, normally a semantic token such as
 * `var(--color-success)`, never a raw hex.
 */
export function ToneBadge({
  label,
  color,
  size = "sm",
  title,
  srLabel,
  testId,
  wrap = false,
}: {
  label: string;
  color: string;
  /** `xs` is the dense in-row pill (injury code). */
  size?: "sm" | "xs";
  title?: string;
  /** Full text for screen readers when `label` is an abbreviation. */
  srLabel?: string;
  testId?: string;
  /** Let a long sentence-style label wrap inside its container instead of widening the page. Multi-word labels wrap on their own (200% text, narrow rows). */
  wrap?: boolean;
}) {
  return (
    <span
      data-testid={testId}
      title={title}
      className={`${size === "xs" ? "px-1.5 text-[0.6875rem] leading-4 inline-flex items-center" : "px-1.5 py-0.5 text-xs"} font-extrabold uppercase ${wrap || label.includes(" ") ? "min-w-0 max-w-full break-words" : label.length <= 4 ? "whitespace-nowrap shrink-0" : "min-w-0 max-w-full [overflow-wrap:anywhere]"}`}
      style={{
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} var(--chip-fill-pct, 15%), transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} var(--chip-ring-pct, 0%), transparent)`,
        // Ink: the tone mixed toward the primary text color so small tinted pills clear AA (4.5:1) in both themes.
        color: `color-mix(in srgb, ${color} 80%, var(--color-text-primary))`,
        letterSpacing: "var(--letter-spacing-badge)",
      }}
    >
      {srLabel ? (
        <>
          <span aria-hidden="true">{label}</span>
          <span className="sr-only">{srLabel}</span>
        </>
      ) : (
        label
      )}
    </span>
  );
}
