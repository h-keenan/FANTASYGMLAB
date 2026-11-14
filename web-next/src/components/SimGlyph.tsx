import type { SimGlyphName } from "@/lib/simGame";

/**
 * Section and status glyphs for the GM game. Plain inline SVG with
 * `currentColor` strokes on the same 16px grid as SnapshotTileGlyph and
 * EventTypeGlyph (the app has no icon library), tinted by the caller with a
 * semantic color token. mobile/src/components/SimGlyph.tsx maps the same
 * names to Ionicons.
 */
export function SimGlyph({ name, size = 16 }: { name: SimGlyphName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  switch (name) {
    case "matchup":
      // Two opposing chevrons: head to head.
      return (
        <svg {...common}>
          <path d="M2.5 3.5L6.5 8l-4 4.5M13.5 3.5L9.5 8l4 4.5" />
        </svg>
      );
    case "checklist":
      return (
        <svg {...common}>
          <path d="M5.5 2.5h5v2h-5zM4 3.5H3v10h10v-10h-1" />
          <path d="M5.5 9l1.8 1.8 3.2-3.6" />
        </svg>
      );
    case "waiver":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M8 5v6M5 8h6" />
        </svg>
      );
    case "bye":
      return (
        <svg {...common}>
          <path d="M3 4.5h10v8.5H3zM3 7.5h10M6 2.5v3M10 2.5v3" />
          <path d="M6.5 9.5l3 2M9.5 9.5l-3 2" />
        </svg>
      );
    case "injury":
      return (
        <svg {...common}>
          <path d="M8 2.5v11M2.5 8h11" />
        </svg>
      );
    case "trade":
      return (
        <svg {...common}>
          <path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" />
        </svg>
      );
    case "standings":
      return (
        <svg {...common}>
          <path d="M3 13.5V9M8 13.5V3.5M13 13.5V7" />
        </svg>
      );
    case "hot":
      return (
        <svg {...common}>
          <path d="M8 1.8c.5 2.3 3.6 3.5 3.6 6.8a3.6 3.6 0 01-7.2 0c0-1.4.6-2.3 1.4-3.1.2 1 .7 1.6 1.3 1.9-.2-2 .1-3.6.9-5.6z" />
        </svg>
      );
    case "cold":
      return (
        <svg {...common}>
          <path d="M8 2v12M2.8 5l10.4 6M2.8 11l10.4-6" />
        </svg>
      );
    case "league":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" />
          <path d="M2 8h12M8 2c-2.6 2.2-2.6 9.8 0 12M8 2c2.6 2.2 2.6 9.8 0 12" />
        </svg>
      );
    case "team":
      return (
        <svg {...common}>
          <path d="M8 1.8l5 1.9v4c0 3.4-2.1 5.9-5 6.8-2.9-.9-5-3.4-5-6.8v-4z" />
        </svg>
      );
    case "check":
      return (
        <svg {...common}>
          <path d="M3.5 8.5l3 3 6-6.5" />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path d="M8 2L14.5 13.5h-13zM8 6.5v3.2M8 11.7v.1" />
        </svg>
      );
    case "spark":
      return (
        <svg {...common}>
          <path d="M8 1.5l1.6 4.4 4.4 1.6-4.4 1.6L8 13.5 6.4 9.1 2 7.5l4.4-1.6z" />
        </svg>
      );
    case "trophy":
      return (
        <svg {...common}>
          <path d="M5 2.5h6v3.5a3 3 0 0 1-6 0zM5 3.5H2.5v1a2.2 2.2 0 0 0 2.6 2.1M11 3.5h2.5v1a2.2 2.2 0 0 1-2.6 2.1M8 9v2.5M5.5 13.5h5" />
        </svg>
      );
    default:
      return null;
  }
}
