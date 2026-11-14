// Shared (web + mobile twin): plain-words presentation of the Fantasy Sim history payloads
// (GET /players/{id}/history and /teams/{id}/history). Pure and import-free of runtime code.

import { simSeasonLabel, type SimHistoryAsset, type SimHistoryEntry, type SimTeamHistoryMove } from "./simGame";

interface When {
  season: number;
  year: number | null;
  /** "S3 2028" when the server built it. */
  season_label?: string;
  week: number;
  offseason: boolean;
}

/** "S3 2028 · Week 5", "Week 5" (first season of a one-season game), "S2 2027 offseason" or "S2 · Week 5" when the game has no calendar year. */
export function simWhenLabel(w: When): string {
  const base = w.season_label || (w.year ? simSeasonLabel(w.season, w.year) : w.season > 1 ? simSeasonLabel(w.season) : "");
  if (w.offseason) return `${base || "Offseason"}${base ? " offseason" : ""}`;
  if (w.week <= 0) return base ? `${base} draft` : "Draft";
  return base ? `${base} · Week ${w.week}` : `Week ${w.week}`;
}

/** "Round 3, pick 31 overall" with the auto-pick note. */
export function simDraftSlotText(round: number | undefined, pick: number | undefined, auto?: boolean): string {
  if (!round || !pick) return "";
  return `Round ${round}, pick ${pick} overall${auto ? " (auto)" : ""}`;
}

const names = (assets: readonly SimHistoryAsset[] | undefined): string => (assets ?? []).map((a) => a.name).join(", ");

/** One sentence for a step in a player's story. */
export function simHistoryText(e: SimHistoryEntry): string {
  const team = e.team_name ?? "a team";
  switch (e.kind) {
    case "drafted": {
      const slot = simDraftSlotText(e.round, e.pick, e.auto);
      const where = e.draft === "rookie" ? `${e.class_season_label || e.class_year ? `${e.class_season_label || e.class_year} ` : ""}rookie draft` : "the league draft";
      return `Drafted by ${team} in ${where}${slot ? `: ${slot}` : ""}${e.via?.team_name ? ` (pick from ${e.via.team_name})` : ""}`;
    }
    case "started":
      return `Started the game on ${team}`;
    case "claimed":
      return `Claimed off waivers by ${team}${e.dropped ? ` (dropped ${e.dropped})` : ""}`;
    case "dropped":
      return `Dropped by ${team}`;
    case "cut":
      return `Cut by ${team}`;
    case "retired":
      return `Retired${e.team_name ? ` from ${e.team_name}` : ""}`;
    case "traded": {
      const from = e.from_team?.team_name ?? "a team";
      const to = e.to_team?.team_name ?? "a team";
      const back = names(e.with_assets);
      return `Traded from ${from} to ${to}${back ? ` for ${back}` : ""}`;
    }
    default:
      return "";
  }
}

/** One sentence for a team's own move. */
export function simTeamMoveText(m: SimTeamHistoryMove): string {
  switch (m.kind) {
    case "trade":
      return `Traded ${names(m.sent) || "nothing"} to ${m.with_team?.team_name ?? "a team"} for ${names(m.received) || "nothing"}`;
    case "claim":
      return `Claimed ${m.added?.name ?? "a player"}${m.dropped ? `, dropped ${m.dropped.name}` : ""}`;
    case "cut":
      return `Cut ${m.player?.name ?? "a player"}`;
    default:
      return `Dropped ${m.player?.name ?? "a player"}${m.reason === "roster_limit" ? " (roster limit)" : ""}`;
  }
}

/** "9-5", "9-5-1" */
export function simSeasonRecord(s: { wins: number; losses: number; ties: number }): string {
  return s.ties ? `${s.wins}-${s.losses}-${s.ties}` : `${s.wins}-${s.losses}`;
}
