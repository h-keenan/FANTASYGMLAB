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
