/**
 * GM Plan's Plan Snapshot tiles and trade-deadline banner. Mirrors
 * web-next/src/lib/gmPlanSnapshot.ts. A tile is omitted (never filled with
 * a placeholder) when its source value is missing; "Proj. N-seed" appears
 * only when the playoff simulation returned a median seed.
 */

export interface SnapshotRanking {
  power_rank: number | null;
  draft_capital_rank: number | null;
  starter_rank: number | null;
  bench_rank: number | null;
  age_rank: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
}

export interface SnapshotOdds {
  playoff_probability: number;
  median_seed?: number | null;
}

export interface PlanSnapshotTile {
  key: 'power' | 'capital' | 'odds' | 'record' | 'starter' | 'bench' | 'age';
  label: string;
  value: string;
  /** 0-1 progress, null when the tile has no bar (Record). */
  fill: number | null;
  note?: string;
}

function rankTile(
  key: PlanSnapshotTile['key'],
  label: string,
  rank: number | null | undefined,
  total: number,
): PlanSnapshotTile | null {
  if (rank === null || rank === undefined || total <= 0) return null;
  return { key, label, value: `${rank} of ${total}`, fill: Math.max(0, Math.min(1, (total - rank + 1) / total)) };
}

export function buildPlanSnapshot(
  ranking: SnapshotRanking | null,
  totalTeams: number,
  odds: SnapshotOdds | null,
): PlanSnapshotTile[] {
  const tiles: Array<PlanSnapshotTile | null> = [];
  if (ranking) {
    tiles.push(rankTile('power', 'Roster Power', ranking.power_rank, totalTeams));
    tiles.push(rankTile('capital', 'Draft Capital Rank', ranking.draft_capital_rank, totalTeams));
  }
  if (odds && Number.isFinite(odds.playoff_probability)) {
    tiles.push({
      key: 'odds',
      label: 'Playoff Odds',
      value: `${Math.round(odds.playoff_probability)}%`,
      fill: Math.max(0, Math.min(1, odds.playoff_probability / 100)),
      note: odds.median_seed ? `Proj. ${odds.median_seed}-seed` : undefined,
    });
  }
  if (ranking) {
    const { wins, losses, ties } = ranking;
    if (wins !== null && wins !== undefined && losses !== null && losses !== undefined) {
      tiles.push({
        key: 'record',
        label: 'Record',
        value: ties ? `${wins} - ${losses} - ${ties}` : `${wins} - ${losses}`,
        fill: null,
      });
    }
    tiles.push(rankTile('starter', 'Starter Strength', ranking.starter_rank, totalTeams));
    tiles.push(rankTile('bench', 'Bench Depth', ranking.bench_rank, totalTeams));
    tiles.push(rankTile('age', 'Roster Age', ranking.age_rank, totalTeams));
  }
  return tiles.filter((tile): tile is PlanSnapshotTile => tile !== null);
}

/** The deadline week while it is still ahead; null once passed or unknown. */
export function deadlineWeek(
  window: { trade_deadline_week: number | null; trade_deadline_passed: boolean } | null | undefined,
): number | null {
  if (!window || window.trade_deadline_passed) return null;
  return window.trade_deadline_week ?? null;
}
