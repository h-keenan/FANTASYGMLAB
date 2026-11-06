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
  /** Let a long sentence-style label wrap inside its container instead of widening the page. */
  wrap?: boolean;
}) {
  return (
    <span
      data-testid={testId}
      title={title}
      className={`${size === "xs" ? "px-1.5 text-[0.625rem] leading-4 inline-flex items-center" : "px-1.5 py-0.5 text-xs"} font-extrabold uppercase ${wrap ? "min-w-0 max-w-full break-words" : "whitespace-nowrap shrink-0"}`}
      style={{
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} var(--chip-fill-pct, 15%), transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} var(--chip-ring-pct, 0%), transparent)`,
        color,
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
