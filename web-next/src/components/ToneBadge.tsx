/**
 * The one status badge: a small uppercase rounded pill tinted from one
 * semantic color (15% fill of the same color as the text). Owner decision
 * (docs/ui-module-inventory.md B9): rounded pill everywhere. Position badges
 * are the single exception and live in `PositionBadge`.
 *
 * `color` is a CSS color expression, normally a semantic token such as
 * `var(--color-success)`, never a raw hex.
 */
export function ToneBadge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="px-1.5 py-0.5 text-xs font-extrabold uppercase whitespace-nowrap shrink-0"
      style={{
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
        letterSpacing: "var(--letter-spacing-badge)",
      }}
    >
      {label}
    </span>
  );
}
