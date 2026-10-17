/**
 * Icons for the Premium page — coridian_, 2026-10-17 (screenshot of the
 * real pricing cards): "need more glyph icons and visualizations." Every
 * feature line was a plain bullet dot with no icon, same gap the dashboard
 * had before SnapshotTileGlyph (coridian_, 2026-10-16: "the dashboard needs
 * more glyph icons... so people can quickly scan the page"). Plain inline
 * SVG (`currentColor` strokes), same approach as every other glyph set in
 * this app — no icon library installed to warrant adding one for a
 * handful of fixed glyphs.
 */

export function FeatureIncludedGlyph({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.3" />
      <path d="M5.3 8.2l1.9 1.9 3.6-4" />
    </svg>
  );
}

export type PlanTierGlyphName = "pro" | "front_office";

export function PlanTierGlyph({ name, size = 16 }: { name: PlanTierGlyphName; size?: number }) {
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

  if (name === "front_office") {
    // Shield — same "serious, protected, top-tier" read as Team Snapshot's
    // franchise glyph, not redrawn from scratch.
    return (
      <svg {...common}>
        <path d="M8 1.8l5 1.9v4c0 3.4-2.1 5.9-5 6.8-2.9-.9-5-3.4-5-6.8v-4z" />
      </svg>
    );
  }

  // Star — Pro, the standard paid tier.
  return (
    <svg {...common}>
      <path d="M8 1.6l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.4l-3.8 2 .7-4.3-3.1-3 4.3-.6z" />
    </svg>
  );
}
