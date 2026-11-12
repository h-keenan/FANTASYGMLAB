import type { ReviewGlyph } from "@/lib/simReview";

/**
 * One small stroke glyph per kind of Season in Review card or section. Same
 * recipe as EventTypeGlyph (16px viewBox, currentColor), so the tinted chip
 * around it sets the color.
 */
export function ReviewGlyphIcon({ glyph, size = 16 }: { glyph: ReviewGlyph; size?: number }) {
  const common = {
    width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor",
    strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false,
  };
  switch (glyph) {
    case "lineup": // clipboard
      return <svg {...common}><path d="M5.5 3H4v10.5h8V3h-1.5M6 2h4v2H6zM6 7.5h4M6 10h3" /></svg>;
    case "waiver": // plus in a circle
      return <svg {...common}><circle cx="8" cy="8" r="5.5" /><path d="M8 5.5v5M5.5 8h5" /></svg>;
    case "trade": // swap arrows
      return <svg {...common}><path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" /></svg>;
    case "draft": // ticket / pick
      return <svg {...common}><path d="M2.5 5.5h11v2a1 1 0 000 2v2h-11v-2a1 1 0 000-2zM6.5 5.5v6" /></svg>;
    case "injury": // medical cross
      return <svg {...common}><path d="M8 2.5v11M2.5 8h11" /></svg>;
    case "boom": // rising arrow
      return <svg {...common}><path d="M3 12l3.5-3.5 2 2L13 5M9.5 5H13v3.5" /></svg>;
    case "bust": // falling arrow
      return <svg {...common}><path d="M3 4l3.5 3.5 2-2L13 11M9.5 11H13V7.5" /></svg>;
    case "game": // stopwatch
      return <svg {...common}><circle cx="8" cy="9" r="4.5" /><path d="M8 9V6.5M6.5 2h3" /></svg>;
    case "trophy":
      return <svg {...common}><path d="M5 2.5h6v3.5a3 3 0 01-6 0zM5 4H2.5c0 2 1 3 2.5 3M11 4h2.5c0 2-1 3-2.5 3M8 9v2.5M5.5 13.5h5" /></svg>;
    case "rank": // line chart
      return <svg {...common}><path d="M2.5 3v10.5H13.5M4.5 10l3-3 2 2 3.5-4.5" /></svg>;
    case "leader": // bars
      return <svg {...common}><path d="M3.5 13V9M8 13V3M12.5 13V6" /></svg>;
    case "path": // flag
      return <svg {...common}><path d="M4 2v12M4 3h7.5l-1.8 2.5L11.5 8H4" /></svg>;
    default: // stats
      return <svg {...common}><path d="M3 13V8M6.5 13V4M10 13V7M13.5 13V10" /></svg>;
  }
}
