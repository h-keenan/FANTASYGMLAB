/**
 * Small inline glyphs for the draft room (queue, draft, search, reorder,
 * remove). Plain SVG on `currentColor`, same approach as EventTypeGlyph.
 */
export type SimDraftGlyphName = "queue" | "queued" | "draft" | "search" | "up" | "down" | "remove";

export function SimDraftGlyph({ name, size = 16 }: { name: SimDraftGlyphName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  switch (name) {
    case "queue":
      return (
        <svg {...common}>
          <path d="M2.5 4.5h8M2.5 8h8M2.5 11.5h4M12.5 9.5v4M10.5 11.5h4" />
        </svg>
      );
    case "queued":
      return (
        <svg {...common}>
          <path d="M2.5 4.5h8M2.5 8h8M2.5 11.5h4M10.5 12l1.6 1.6 2.9-3.2" />
        </svg>
      );
    case "draft":
      return (
        <svg {...common}>
          <path d="M3 8.5l3.2 3.2L13 4.5" />
        </svg>
      );
    case "search":
      return (
        <svg {...common}>
          <circle cx="7" cy="7" r="4.2" />
          <path d="M10.2 10.2L13.5 13.5" />
        </svg>
      );
    case "up":
      return (
        <svg {...common}>
          <path d="M4 9.5L8 5.5l4 4" />
        </svg>
      );
    case "down":
      return (
        <svg {...common}>
          <path d="M4 6.5l4 4 4-4" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M4 4l8 8M12 4l-8 8" />
        </svg>
      );
  }
}
