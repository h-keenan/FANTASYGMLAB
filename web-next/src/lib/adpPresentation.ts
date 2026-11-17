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
