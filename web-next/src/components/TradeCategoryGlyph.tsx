/**
 * Small glyph icon per Trade Hub idea category, shown next to the category
 * badge text (coridian_, 2026-10-16: "the title of these trade ideas, like
 * health relief or headline recommendation, etc, all need some sort of
 * glyph icon and or color to them so that they stand out and that they're
 * easily differentiable" — color already existed per-category
 * (tradeHubPresentation.ts's categoryColor, ported from mobile's own
 * categoryColors), but neither mobile nor web ever had a glyph; this is a
 * genuinely new, web-next-only addition, not a port).
 *
 * Plain inline SVG (`currentColor` strokes) rather than a dependency — this
 * app has no icon library installed at all yet, and 8 fixed glyphs don't
 * warrant adding one.
 */
export function TradeCategoryGlyph({ category, size = 13 }: { category: string | null | undefined; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (category) {
    case "Headline Recommendation":
      // Star — the single top pick.
      return (
        <svg {...common}>
          <path d="M8 1.5l1.8 3.9 4.2.5-3.1 3 .8 4.3L8 11.2l-3.7 2 .8-4.3-3.1-3 4.2-.5z" />
        </svg>
      );
    case "Health Relief":
      // Medical cross — replaces an injured/thin position.
      return (
        <svg {...common}>
          <path d="M8 2.5v11M2.5 8h11" />
        </svg>
      );
    case "Draft Capital":
      // Ticket/pick stub.
      return (
        <svg {...common}>
          <rect x="2" y="4.5" width="12" height="7" rx="1" />
          <path d="M6.5 4.5v7M9.5 4.5v7" strokeDasharray="1.4 1.4" />
        </svg>
      );
    case "Age Optimization":
      // Hourglass — timeline/age framing.
      return (
        <svg {...common}>
          <path d="M4 2h8M4 14h8M4.5 2c0 3 2.5 3.5 3.5 4.5 1-1 3.5-1.5 3.5-4.5M4.5 14c0-3 2.5-3.5 3.5-4.5 1 1 3.5 1.5 3.5 4.5" />
        </svg>
      );
    case "Rebuild":
      // Wrench — under-construction framing.
      return (
        <svg {...common}>
          <path d="M10.6 2.4a3 3 0 00-3.95 3.55L2.5 10.1l1.4 1.4 4.15-4.15a3 3 0 003.55-3.95l-1.9 1.9-1.4-.5-.5-1.4z" />
        </svg>
      );
    case "Contender":
      // Trophy — win-now framing.
      return (
        <svg {...common}>
          <path d="M5 2.5h6v3.5a3 3 0 01-6 0z" />
          <path d="M5 3.5H3v1a2.5 2.5 0 002.3 2.5M11 3.5h2v1a2.5 2.5 0 01-2.3 2.5" />
          <path d="M8 9.5v2M5.5 13.5h5l-.6-2h-3.8z" />
        </svg>
      );
    case "Need-Based":
      // Target — fills a roster need.
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="5.5" />
          <circle cx="8" cy="8" r="2.75" />
          <circle cx="8" cy="8" r="0.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "High Confidence":
      // Shield check — the model trusts this one.
      return (
        <svg {...common}>
          <path d="M8 1.8l5 1.9v4c0 3.4-2.1 5.9-5 6.8-2.9-.9-5-3.4-5-6.8v-4z" />
          <path d="M5.8 8l1.6 1.6 2.8-3" />
        </svg>
      );
    default:
      return null;
  }
}
