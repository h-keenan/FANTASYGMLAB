import type { CSSProperties } from "react";

import { overallRatingTint } from "@/lib/playerPresentation";

/** Conic-gradient custom properties aren't part of React's CSSProperties
 * typing, so this narrow cast is the standard escape hatch for CSS custom
 * properties in a style object (same pattern this app's other inline
 * `--token` usages would need). */
type GaugeStyle = CSSProperties & { "--ovr-tint"?: string; "--ovr-pct"?: number };

/**
 * Circular "NN OVR" gauge — ports modules/player_cards.py's
 * overall_rating_gauge_html, the one canonical rendering of a player's
 * overall rating sitewide (coridian_: "the overall ALWAYS needs to be a
 * circular gauge throughout the site", 2026-10-14). Shows no ring/number
 * when `rating` is null, same "no fabricated rating" contract the Python
 * source follows (a thin per-position pool, e.g. an IR'd player, just
 * doesn't get one) — but still reserves the same fixed width/height a
 * real gauge would, rather than collapsing to zero width. coridian_,
 * 2026-10-18, screenshot: IR players with a real value but no OVR badge
 * left every column after it (value, "VALUE" label) shifted out of
 * alignment with rows that do have a badge.
 */
export function OvrGauge({ rating, size = "sm" }: { rating: number | null; size?: "sm" | "md" | "lg" }) {
  if (rating === null || rating === undefined) {
    return <span className={`ovr-gauge-placeholder ovr-gauge--${size}`} aria-hidden="true" />;
  }
  const clamped = Math.max(0, Math.min(99, Math.round(rating)));
  const tint = overallRatingTint(clamped);

  return (
    <span
      className={`ovr-gauge ovr-gauge--${size}`}
      style={{ "--ovr-tint": tint, "--ovr-pct": clamped } as GaugeStyle}
      role="img"
      aria-label={`${clamped} overall rating`}
    >
      <span className="ovr-gauge-value">{clamped}</span>
    </span>
  );
}
