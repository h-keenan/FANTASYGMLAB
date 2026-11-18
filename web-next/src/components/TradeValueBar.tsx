/**
 * Compact "who has the edge" bar for a trade's net value change: a center-anchored track, green fill to the right when you have the
 * edge, muted fill to the left otherwise (never red). Display scale only; the sign comes from `delta`. Mobile twin:
 * mobile/src/components/TradeValueBar.tsx (same saturating curve).
 */
const EDGE_SATURATION_SCALE = 900;

/** Fraction (0-1) of one side of the track a value edge of this size fills; saturates for lopsided trades, 0 when even. */
export function edgeFraction(delta: number, scale: number = EDGE_SATURATION_SCALE): number {
  const magnitude = Math.abs(delta);
  if (!Number.isFinite(magnitude) || magnitude <= 0) return 0;
  return magnitude / (magnitude + scale);
}

export function tradeValueBarLabel(delta: number): string {
  const value = `${delta > 0 ? "+" : ""}${Math.round(delta).toLocaleString()}`;
  if (delta > 0) return `Value edge: ${value}. You have the edge in this trade.`;
  if (delta < 0) return `Value edge: ${value}. Your opponent has the edge in this trade.`;
  return "Value edge: even. Neither side has a clear value edge.";
}

export function TradeValueBar({ delta }: { delta: number }) {
  const fraction = edgeFraction(delta);
  const tone = delta > 0 ? "var(--color-success)" : "var(--color-text-secondary)";
  return (
    <div role="img" aria-label={tradeValueBarLabel(delta)} data-testid="trade-value-bar">
      <div className="relative overflow-hidden" style={{ height: 6, borderRadius: "var(--radius-pill)", background: "var(--color-border)" }}>
        <div className="absolute" style={{ left: "50%", top: -1, bottom: -1, width: 2, marginLeft: -1, background: "var(--color-border-strong)" }} />
        {fraction > 0 ? (
          <div
            className="absolute"
            style={{ top: 0, bottom: 0, background: tone, borderRadius: "var(--radius-pill)", width: `${fraction * 50}%`, ...(delta > 0 ? { left: "50%" } : { right: "50%" }) }}
          />
        ) : null}
      </div>
    </div>
  );
}
