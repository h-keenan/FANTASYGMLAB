/**
 * ADP display helpers (Fantasy Football Calculator feed; see modules/rookie_adp.py).
 * Mirrored by mobile/src/lib/adpPresentation.ts. Real 1QB ADP is always labelled "1QB ADP";
 * the superflex number is a model ("Est. SF") and is never shown without that label and a "?" note.
 */
export interface AdpFields {
  adp: number | null;
  adp_label?: string | null;
  adp_est_sf?: number | null;
  adp_est_sf_label?: string | null;
}

export const EST_SF_NOTE =
  "Estimated, not real ADP: Fantasy Football Calculator's 1QB ADP re-ordered with our superflex vs 1QB QB values. No approved source publishes real superflex ADP.";
export const ADP_CREDIT = "ADP: Fantasy Football Calculator";
export const ADP_CREDIT_URL = "https://fantasyfootballcalculator.com/adp";

export function formatAdp(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "-" : value.toFixed(1);
}

/** Parts to render: the real ADP always first, the modeled estimate (if any) second and flagged. */
export function adpParts(f: AdpFields): { real: string | null; est: string | null } {
  return {
    real: f.adp == null ? null : `${f.adp_label || "1QB ADP"} ${formatAdp(f.adp)}`,
    est: f.adp == null || f.adp_est_sf == null ? null : `${f.adp_est_sf_label || "Est. SF"} ${formatAdp(f.adp_est_sf)}`,
  };
}

export function deltaText(delta: number | null | undefined): string {
  return delta == null ? "-" : `${delta > 0 ? "+" : ""}${delta}`;
}

/** One-line context string for list rows: "1QB ADP 4.2 · Est. SF 2.0 (?)" (no "?" tap target in plain text). */
export function adpContext(f: AdpFields): string {
  const { real, est } = adpParts(f);
  return real ? (est ? `${real} · ${est} (?)` : real) : '';
}

export const ROOKIE_BOARD_TITLE = "Rookie Board vs ADP";
export const ROOKIE_BOARD_NO_ADP_NOTE = "Rookie ADP is published only during rookie-draft season. Our rookie ranks are shown without a market number.";

export interface RookieBoardRowFields {
  name: string;
  adp: number | null;
  verdict?: string | null;
  delta?: number | null;
}

export interface RookieBoardSummaryPart {
  key: string;
  text: string;
  strong?: boolean;
  tone?: "accent" | "muted";
}

/** The collapsed summary chips of the rookie board, shared by web and app: count with ADP, the top value pick, the basis. */
export function rookieBoardSummaryParts(rows: readonly RookieBoardRowFields[]): RookieBoardSummaryPart[] {
  const withAdp = rows.filter((row) => row.adp != null);
  const topValue = withAdp.filter((row) => row.verdict === "value").sort((a, b) => (b.delta ?? 0) - (a.delta ?? 0))[0];
  const parts: Array<RookieBoardSummaryPart | null> = [
    { key: "n", text: withAdp.length ? `${withAdp.length} with ADP` : "No ADP yet", strong: true },
    topValue ? { key: "v", text: `Value: ${topValue.name} (${deltaText(topValue.delta)})`, tone: "accent" } : null,
    { key: "s", text: "Our rank vs market", tone: "muted" },
  ];
  return parts.filter((part): part is RookieBoardSummaryPart => part != null);
}
