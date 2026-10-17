export type SnapshotGlyphName = "record" | "power" | "franchise" | "starter" | "bench" | "age" | "injury";

/**
 * Small glyph per Team Snapshot tile — coridian_, 2026-10-17: "the dashboard
 * needs more glyph icons and text accents so people can quickly scan the
 * page." Every tile here previously had a plain text label and no icon at
 * all. Plain inline SVG (`currentColor` strokes), same approach as
 * TradeCategoryGlyph — this app has no icon library installed for 7 fixed
 * glyphs to warrant adding one.
 */
export function SnapshotTileGlyph({ name, size = 13 }: { name: SnapshotGlyphName; size?: number }) {
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

  switch (name) {
    case "record":
      // Flag — wins/losses record.
      return (
        <svg {...common}>
          <path d="M3.5 1.5v13" />
          <path d="M3.5 2.5h8.5l-2 2.5 2 2.5h-8.5" />
        </svg>
      );
    case "power":
      // Trophy — overall power rank.
      return (
        <svg {...common}>
          <path d="M5 2h6v3.5a3 3 0 01-6 0z" />
          <path d="M5 3H3v1a2.5 2.5 0 002.3 2.5M11 3h2v1a2.5 2.5 0 01-2.3 2.5" />
          <path d="M8 9v2M5.5 13h5l-.6-2h-3.8z" />
        </svg>
      );
    case "franchise":
      // Shield — long-term franchise strength.
      return (
        <svg {...common}>
          <path d="M8 1.8l5 1.9v4c0 3.4-2.1 5.9-5 6.8-2.9-.9-5-3.4-5-6.8v-4z" />
        </svg>
      );
    case "starter":
      // Football — starter lineup strength.
      return (
        <svg {...common}>
          <ellipse cx="8" cy="8" rx="6.2" ry="4" transform="rotate(-25 8 8)" />
          <path d="M5.3 7.2l5.4 1.6" />
        </svg>
      );
    case "bench":
      // Stacked layers — bench depth.
      return (
        <svg {...common}>
          <path d="M8 2l6 3-6 3-6-3z" />
          <path d="M2 9l6 3 6-3" />
        </svg>
      );
    case "age":
      // Hourglass — roster age.
      return (
        <svg {...common}>
          <path d="M4 2h8M4 14h8M4.5 2c0 3 2.5 3.5 3.5 4.5 1-1 3.5-1.5 3.5-4.5M4.5 14c0-3 2.5-3.5 3.5-4.5 1 1 3.5 1.5 3.5 4.5" />
        </svg>
      );
    case "injury":
      // Medical cross — health status.
      return (
        <svg {...common}>
          <path d="M8 2.5v11M2.5 8h11" />
        </svg>
      );
    default:
      return null;
  }
}
