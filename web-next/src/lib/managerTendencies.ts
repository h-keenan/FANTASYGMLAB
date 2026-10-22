import { api, type ManagerTendenciesSummaryResponse, type ManagerTendencySummaryRow } from "./api";

/** Signal order + short titles for the manager profile (mirrors
 * modules.manager_tendencies.SIGNAL_ORDER). */
export const TENDENCY_SIGNALS: Array<[string, string]> = [
  ["posture", "Posture"],
  ["position_preference", "Positions"],
  ["age_preference", "Age"],
  ["pick_behavior", "Picks"],
  ["package_shape", "Package shape"],
  ["trade_frequency", "Trade rate"],
  ["waiver_activity", "Waivers"],
  ["trade_partners", "Partners"],
];

/** Splits a server headline into short chips, dropping the "not enough
 * trades"/"no strong tendencies" lead-ins so only real reads remain. */
export function headlineChips(headline: string | null | undefined, max = 3): string[] {
  return (headline ?? "")
    .split(/\.\s+|\.$/)
    .map((part) => part.trim())
    .filter((part) => part && !/^(not enough|no strong|no owner)/i.test(part))
    .slice(0, max);
}

const TTL_MS = 5 * 60 * 1000;
const cache = new Map<string, { at: number; promise: Promise<ManagerTendenciesSummaryResponse> }>();

/** One request per league, shared by every card on the page. */
export function loadLeagueTendencies(leagueId: string): Promise<ManagerTendenciesSummaryResponse> {
  const hit = cache.get(leagueId);
  if (hit && Date.now() - hit.at < TTL_MS) return hit.promise;
  const promise = api.getManagerTendencies(leagueId);
  cache.set(leagueId, { at: Date.now(), promise });
  promise.catch(() => cache.delete(leagueId));
  return promise;
}

export function findManagerRow(
  data: ManagerTendenciesSummaryResponse,
  match: { rosterId?: string | number; teamName?: string },
): ManagerTendencySummaryRow | undefined {
  if (match.rosterId !== undefined && match.rosterId !== "") {
    const byId = data.managers.find((m) => String(m.roster_id) === String(match.rosterId));
    if (byId) return byId;
  }
  const name = (match.teamName ?? "").trim().toLowerCase();
  return name ? data.managers.find((m) => (m.team_name ?? "").trim().toLowerCase() === name) : undefined;
}

export type TendencyTone = "success" | "warning" | "accent" | "premium";

const LABEL_TONES: Record<string, TendencyTone> = {
  contending: "success",
  very_active_on_waivers: "success",
  trades_more_than_most: "success",
  aggressive_faab: "success",
  rebuilding: "warning",
  quiet_on_waivers: "warning",
  trades_less_than_most: "warning",
  conservative_faab: "warning",
  buys_picks: "accent",
  acquires_younger: "accent",
  consolidates: "accent",
  has_frequent_partners: "accent",
  sells_picks: "premium",
  acquires_older: "premium",
  splits: "premium",
};

/** Semantic tone for a signal label (server label slugs, never made up). */
export function tendencyTone(label: string | null | undefined): TendencyTone {
  return (label && LABEL_TONES[label]) || "accent";
}

/** "very_active_on_waivers" -> "Very active on waivers"; null for no label. */
export function tendencyBadgeText(label: string | null | undefined): string | null {
  if (!label) return null;
  const text = label.replace(/_/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : null;
}

/** Evidence meter fill (0-1): sample size against the signal's minimum, capped. */
export function sampleFill(sampleSize: number, minSample: number): number {
  const target = Math.max(1, minSample) * 2;
  return Math.max(0, Math.min(1, sampleSize / target));
}
