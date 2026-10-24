import type { CSSProperties } from "react";

type RingStyle = CSSProperties & { "--value-ring-pct"?: number; "--value-ring-tone"?: string };

/**
 * The one circular ring (value percentile, overall rating). Conic-gradient
 * plus a punched-out center, styled in globals.css (`.value-ring*`). Color
 * comes from `tone` (red/gold/green semantic bands) or, for a continuous
 * scale such as a player's OVR, an explicit `tint`. Confidence is NOT a ring:
 * it is always the segmented ConfidenceMeter.
 *
 * Sizes by diameter: xs 1.65rem, sm 2.5rem, md 3.25rem, lg 4.5rem (default).
 */
export function ValueRing({
  percent,
  tone = "mid",
  tint,
  display,
  ariaLabel,
  size = "lg",
}: {
  /** 0-100, or null to render the "—" unavailable state. */
  percent: number | null;
  tone?: "low" | "mid" | "high";
  /** CSS color expression that overrides `tone`. */
  tint?: string;
  /** The text inside the ring (e.g. "72" or "—"). */
  display: string;
  ariaLabel: string;
  size?: "xs" | "sm" | "md" | "lg";
}) {
  return (
    <span
      className={`value-ring value-ring--${tone}${size === "lg" ? "" : ` value-ring--${size}`}`}
      style={{ "--value-ring-pct": percent ?? 0, ...(tint ? { "--value-ring-tone": tint } : null) } as RingStyle}
      role="img"
      aria-label={ariaLabel}
    >
      <span className="value-ring-value">{display}</span>
    </span>
  );
}
