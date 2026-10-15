import type { CSSProperties } from "react";

type RingStyle = CSSProperties & { "--value-ring-pct"?: number };

/**
 * Generic circular percent ring — ports modules/my_team_ui.py's
 * team_snapshot_html (.mt-value-ring) conic-gradient mechanism. Extracted
 * (Revision 3 CSS-cleanup pass) from MyTeamContent.tsx's local
 * `TeamValueRing` so Trade Hub's confidence/realism rings can reuse the same
 * primitive instead of inventing a second ring component — same
 * conic-gradient + punched-out-center technique, same red/gold/green tone
 * vocabulary (`.value-ring--low/mid/high`), just parameterized by whatever
 * percent + tone + label the caller already computed server-side (team
 * value percentile for My Team, confidence/realism ring percent for Trade
 * Hub — see lib/tradeHubPresentation.ts).
 */
export function ValueRing({
  percent,
  tone,
  display,
  ariaLabel,
  size = "md",
}: {
  /** 0-100, or null to render the "—" unavailable state. */
  percent: number | null;
  tone: "low" | "mid" | "high";
  /** The text inside the ring (e.g. "72" or "—"). */
  display: string;
  ariaLabel: string;
  size?: "sm" | "md";
}) {
  return (
    <div
      className={`value-ring value-ring--${tone}${size === "sm" ? " value-ring--sm" : ""}`}
      style={{ "--value-ring-pct": percent ?? 0 } as RingStyle}
      role="img"
      aria-label={ariaLabel}
    >
      <span className="value-ring-value">{display}</span>
    </div>
  );
}
