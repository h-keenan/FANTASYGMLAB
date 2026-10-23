/**
 * IDP (individual defensive player) presentation for Players. Pure functions
 * only, so the page stays rendering.
 *
 * IDP rows come from GET .../idp/values, which only returns rows for leagues
 * that start DL/LB/DB/IDP_FLEX; every other league gets `idp: false` and this
 * module hands back nothing, so non-IDP leagues see no change. Values are
 * model values on the same 0-10,000 scale as offensive values (see
 * docs/idp-model-backtest.md) - they are adapted to the existing RankedPlayer
 * shape so the shared Players row, sort and filter code render them unchanged.
 */
import type { LeagueIdpValuesResponse, RankedPlayer } from "./api";

export const IDP_POSITION_FILTERS = ["DL", "LB", "DB"] as const;

export function isIdpPositionFilter(position: string): boolean {
  return (IDP_POSITION_FILTERS as readonly string[]).includes(position);
}

/** True only for a league that starts defenders AND has values to show. */
export function hasIdpValues(idp: LeagueIdpValuesResponse | null | undefined): boolean {
  return Boolean(idp && idp.idp && idp.players.length > 0);
}

/** Position filter options: offense always, defense chips only in IDP leagues. */
export function playersPositionOptions(
  base: readonly string[],
  idp: LeagueIdpValuesResponse | null | undefined,
): string[] {
  return hasIdpValues(idp) ? [...base, ...IDP_POSITION_FILTERS] : [...base];
}

/** IDP rows adapted to RankedPlayer. `score` is the model value; `position`
 * is the DL/LB/DB family (what lineup slots use), not DE/CB/S. */
export function idpRowsAsRankedPlayers(idp: LeagueIdpValuesResponse | null | undefined): RankedPlayer[] {
  if (!hasIdpValues(idp)) return [];
  return idp!.players.map((row) => ({
    player_id: row.player_id,
    name: row.name,
    position: row.family,
    team: row.team,
    age: row.age,
    status: "Active",
    injury_status: row.injury_status,
    tier: null,
    score: row.value,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: null,
    stats: [
      { key: "idp_ppg", label: "Proj PPG", value: row.ppg, format: "ppg", percentile: null },
      { key: "idp_por", label: "Pts vs repl", value: row.points_over_replacement, format: "points", percentile: null },
    ],
  }));
}

export const IDP_CONFIDENCE_LABEL: Record<string, string> = {
  high: "Solid sample",
  medium: "Some sample",
  low: "Thin sample",
};

/** One honest line under the list: what these numbers are and what is not counted. */
export function idpMethodNote(idp: LeagueIdpValuesResponse | null | undefined): string | null {
  if (!hasIdpValues(idp)) return null;
  const keys = idp!.unscored_keys ?? [];
  const unscored = keys.length ? ` Not counted: ${keys.join(", ")}.` : "";
  return `IDP values are model estimates from this league's own scoring, not market prices.${unscored}`;
}

/** Waivers / My Team position choices: defense chips only when the league
 * response actually carries defenders (IDP leagues), else `base` unchanged. */
export function withIdpPositionOptions(base: readonly string[], idpRows: readonly unknown[] | null | undefined): string[] {
  return idpRows && idpRows.length > 0 ? [...base, ...IDP_POSITION_FILTERS] : [...base];
}

/** Defenders as Trade Analyzer pool rows: valued ones at their model value,
 * below-replacement ones with `score: null` (shown as a dash, never a made-up
 * number). Empty for non-IDP leagues. Needs the response fetched with
 * `includeBelow` for the below-replacement rows. */
export function idpTradePoolPlayers(idp: LeagueIdpValuesResponse | null | undefined): RankedPlayer[] {
  if (!idp || !idp.idp) return [];
  const below: RankedPlayer[] = (idp.below_replacement_players ?? []).map((row) => ({
    player_id: row.player_id,
    name: row.name,
    position: row.family,
    team: row.team,
    age: row.age,
    status: "Active",
    injury_status: row.injury_status,
    tier: null,
    score: null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: null,
  }));
  return [...idpRowsAsRankedPlayers(idp), ...below];
}

/** Trade Analyzer position chips: defense appears only when the pool has defenders. */
export function tradePositionOptions(base: readonly string[], pool: readonly { position?: string | null }[]): string[] {
  const hasIdp = pool.some((p) => isIdpPositionFilter((p.position ?? "").toUpperCase()));
  return hasIdp ? [...base, ...IDP_POSITION_FILTERS] : [...base];
}
