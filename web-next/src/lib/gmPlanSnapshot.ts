import type { PlayoffOddsTeam, TeamRanking, TradeWindow } from "@/lib/api";

/** One Plan Snapshot tile. `fill` (0-1) drives the progress bar. */
export interface PlanSnapshotTile {
  key: "power" | "capital" | "odds" | "record" | "starter" | "bench" | "age";
  label: string;
  /** Main text, e.g. "3 of 12" or "2 - 4" or "55%". */
  value: string;
  fill: number | null;
  note?: string;
}

function rankTile(
  key: PlanSnapshotTile["key"],
  label: string,
  rank: number | null | undefined,
  total: number,
): PlanSnapshotTile | null {
  if (rank === null || rank === undefined || total <= 0) return null;
  return { key, label, value: `${rank} of ${total}`, fill: Math.max(0, Math.min(1, (total - rank + 1) / total)) };
}

/**
 * Plan Snapshot tiles from the same team-rankings row and playoff-odds row
 * the Dashboard and Playoff Odds screens read. A tile is omitted (never
 * filled with a placeholder) when its source value is missing. The "Proj.
 * N-seed" note appears only when the simulation returned a median seed.
 */
export function buildPlanSnapshot(
  ranking: TeamRanking | null,
  totalTeams: number,
  odds: PlayoffOddsTeam | null,
): PlanSnapshotTile[] {
  const tiles: Array<PlanSnapshotTile | null> = [];
  if (ranking) {
    tiles.push(rankTile("power", "Roster Power", ranking.power_rank, totalTeams));
    tiles.push(rankTile("capital", "Draft Capital Rank", ranking.draft_capital_rank, totalTeams));
  }
  if (odds && Number.isFinite(odds.playoff_probability)) {
    tiles.push({
      key: "odds",
      label: "Playoff Odds",
      value: `${Math.round(odds.playoff_probability)}%`,
      fill: Math.max(0, Math.min(1, odds.playoff_probability / 100)),
      note: odds.median_seed ? `Proj. ${odds.median_seed}-seed` : undefined,
    });
  }
  if (ranking) {
    const wins = ranking.wins;
    const losses = ranking.losses;
    if (wins !== null && wins !== undefined && losses !== null && losses !== undefined) {
      tiles.push({
        key: "record",
        label: "Record",
        value: ranking.ties ? `${wins} - ${losses} - ${ranking.ties}` : `${wins} - ${losses}`,
        fill: null,
      });
    }
    tiles.push(rankTile("starter", "Starter Strength", ranking.starter_rank, totalTeams));
    tiles.push(rankTile("bench", "Bench Depth", ranking.bench_rank, totalTeams));
    tiles.push(rankTile("age", "Roster Age", ranking.age_rank, totalTeams));
  }
  return tiles.filter((tile): tile is PlanSnapshotTile => tile !== null);
}

export type DeadlineBanner = { kind: "upcoming"; week: number } | null;

/** Banner shows only while the league's real trade deadline is still ahead. */
export function deadlineBanner(window: TradeWindow | null | undefined): DeadlineBanner {
  if (!window || window.trade_deadline_passed) return null;
  if (window.trade_deadline_week === null || window.trade_deadline_week === undefined) return null;
  return { kind: "upcoming", week: window.trade_deadline_week };
}
