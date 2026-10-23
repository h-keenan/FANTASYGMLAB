/**
 * Canonical player/position presentation helpers shared by every card that
 * shows a position badge or an overall-rating gauge (GamePlanCard, My Team's
 * Roster Core/Depth and Position Groups). One source of truth instead of
 * each card hand-keeping its own copy of the position->color map, matching
 * the "consolidate the CSS/visual code" direction carried over from
 * Revision 1 (see modules/football_assets.py / modules/player_cards.py on
 * the Streamlit side, which this file mirrors for web-next).
 */

/** position (any case, "DEF"/"DST"/"D/ST" all included) -> the
 * `--color-position-*` CSS variable name defined in globals.css. */
export const POSITION_COLOR_VAR: Record<string, string> = {
  QB: "--color-position-qb",
  RB: "--color-position-rb",
  WR: "--color-position-wr",
  TE: "--color-position-te",
  K: "--color-position-k",
  DEF: "--color-position-dst",
  DST: "--color-position-dst",
  "D/ST": "--color-position-dst",
  // IDP lanes (new for the pill redesign) + the shared neutral "flex" lane
  // for lineup slots that are not a single position.
  DL: "--color-position-dl",
  DE: "--color-position-dl",
  DT: "--color-position-dl",
  LB: "--color-position-lb",
  OLB: "--color-position-lb",
  ILB: "--color-position-lb",
  DB: "--color-position-db",
  CB: "--color-position-db",
  S: "--color-position-db",
  FLEX: "--color-position-flex",
  SUPER_FLEX: "--color-position-flex",
  SUPERFLEX: "--color-position-flex",
  REC_FLEX: "--color-position-flex",
  "WR/RB": "--color-position-flex",
  "WR/TE": "--color-position-flex",
  "RB/WR/TE": "--color-position-flex",
  IDP_FLEX: "--color-position-flex",
  BN: "--color-position-flex",
  IR: "--color-position-flex",
  TAXI: "--color-position-flex",
};

/** Short pill text so every position/slot fits the same pill width
 * (SUPER_FLEX -> SF, IDP_FLEX -> IDP, D/ST -> DEF). Mirrors
 * mobile/src/theme.ts positionBadgeLabel. */
export function positionBadgeLabel(position: string): string {
  const label = position.trim().toUpperCase();
  if (label === "SUPER_FLEX" || label === "SUPERFLEX") return "SF";
  if (label === "WR/RB") return "W/R";
  if (label === "REC_FLEX") return "W/T";
  if (label === "IDP_FLEX") return "IDP";
  if (label === "DST" || label === "D/ST") return "DEF";
  return label;
}

/** position -> the `.position-text-*` className defined in globals.css
 * (ports modules/football_assets.py's position_text_html — a position NAME
 * appearing as plain body text, not inside its own badge chip). */
const POSITION_TEXT_CLASS: Record<string, string> = {
  QB: "position-text-qb",
  QUARTERBACK: "position-text-qb",
  RB: "position-text-rb",
  RUNNINGBACK: "position-text-rb",
  WR: "position-text-wr",
  WIDERECEIVER: "position-text-wr",
  TE: "position-text-te",
  TIGHTEND: "position-text-te",
  K: "position-text-k",
  KICKER: "position-text-k",
  DEF: "position-text-dst",
  DST: "position-text-dst",
  "D/ST": "position-text-dst",
  DEFENSE: "position-text-dst",
};

export function positionColorVar(position: string | null | undefined): string | undefined {
  if (!position) return undefined;
  return POSITION_COLOR_VAR[position.toUpperCase()];
}

/** className to color a plain-text position mention, or undefined for
 * anything that isn't a recognized position (e.g. "No urgent need") —
 * mirrors position_text_html's escape-only fallback. */
export function positionTextClass(label: string | null | undefined): string | undefined {
  if (!label) return undefined;
  const compact = label.toUpperCase().replace(/[\s/]/g, "");
  return POSITION_TEXT_CLASS[label.toUpperCase()] ?? POSITION_TEXT_CLASS[compact];
}

/**
 * Continuous red -> gold -> green tint for the circular OVR gauge —
 * byte-for-byte port of modules/player_cards.py's
 * _overall_rating_tint_css. `rating` is the 0-99 overall rating.
 */
export function overallRatingTint(rating: number): string {
  const clamped = Math.max(0, Math.min(100, Math.round(rating)));
  if (clamped <= 50) {
    const toPct = Math.round((clamped / 50) * 100);
    return `color-mix(in srgb, var(--color-premium) ${toPct}%, var(--color-danger) ${100 - toPct}%)`;
  }
  const toPct = Math.round(((clamped - 50) / 50) * 100);
  return `color-mix(in srgb, var(--color-success) ${toPct}%, var(--color-premium) ${100 - toPct}%)`;
}

/**
 * Best team in a group of `totalTeams` -> 100, worst -> 0 — same transform
 * as modules/league_workspace_ui.py's _percentile_from_rank (and mobile's
 * percentileFromRank). Null when the inputs can't support a real
 * percentile, so a caller renders nothing rather than a fabricated ring.
 */
export function percentileFromRank(rank: number | null, totalTeams: number | null): number | null {
  if (rank === null || rank === undefined || rank <= 0) return null;
  if (totalTeams === null || totalTeams === undefined || totalTeams <= 1) return null;
  return ((totalTeams - rank) / (totalTeams - 1)) * 100;
}

/** Red/gold/green percentile banding — same thresholds as
 * modules/league_workspace_ui.py's _metric_tone_band. */
export function metricToneBand(percentile: number | null): "low" | "mid" | "high" | "" {
  if (percentile === null || percentile === undefined) return "";
  if (percentile < 34) return "low";
  if (percentile < 67) return "mid";
  return "high";
}
