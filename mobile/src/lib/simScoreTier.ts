// Shared (web + mobile twin): how a Fantasy Sim score reads against that position's normal. Pure, import-free.
// One table of "normal" per position (PPR points per game: mean and spread) feeds every tier call, so a 17.5 reads as a
// boom for a running back and as an average week for a quarterback, and a season card, a week chip and a rank all agree.

export type SimScoreTier = "boom" | "average" | "bust";

/** Semantic tone names (the ones CompactModule / ToneBadge already map to colour tokens); average has none (neutral ink). */
export type SimScoreTone = "success" | "warning" | undefined;

interface PosNormal {
  mean: number;
  sd: number;
  /** Starter slots league-wide (12 teams): a rank inside the first third is elite, past the slots is below a starter. */
  slots: number;
}

const NORMAL: Record<string, PosNormal> = {
  QB: { mean: 18, sd: 6, slots: 12 },
  RB: { mean: 11, sd: 6, slots: 24 },
  WR: { mean: 11, sd: 6, slots: 30 },
  TE: { mean: 8, sd: 4.5, slots: 12 },
  K: { mean: 8, sd: 3.2, slots: 12 },
  DEF: { mean: 8, sd: 4, slots: 12 },
  DST: { mean: 8, sd: 4, slots: 12 },
};

const FALLBACK: PosNormal = NORMAL.WR;
const normalFor = (pos: string | null | undefined): PosNormal => NORMAL[String(pos ?? "").toUpperCase()] ?? FALLBACK;

/** One game's points: boom above mean + 0.6 sd, bust below mean - 0.8 sd, otherwise average. */
export function simWeekTier(points: number, pos: string | null | undefined): SimScoreTier {
  const n = normalFor(pos);
  if (!Number.isFinite(points)) return "average";
  if (points >= n.mean + 0.6 * n.sd) return "boom";
  if (points <= n.mean - 0.8 * n.sd) return "bust";
  return "average";
}

/** A season's points per game (averages swing less than single games, so the band is tighter): boom from +0.35 sd, bust from -0.5 sd. */
export function simSeasonTier(ppg: number | null | undefined, pos: string | null | undefined): SimScoreTier {
  if (ppg == null || !Number.isFinite(ppg)) return "average";
  const n = normalFor(pos);
  if (ppg >= n.mean + 0.35 * n.sd) return "boom";
  if (ppg <= n.mean - 0.5 * n.sd) return "bust";
  return "average";
}

/** A position rank (1 = best): top third of the starter slots is a boom, past the slots is a bust. */
export function simRankTier(rank: number | null | undefined, pos: string | null | undefined): SimScoreTier {
  if (rank == null || !Number.isFinite(rank) || rank <= 0) return "average";
  const n = normalFor(pos);
  if (rank <= Math.ceil(n.slots / 3)) return "boom";
  if (rank > n.slots) return "bust";
  return "average";
}

export function simScoreTierTone(tier: SimScoreTier): SimScoreTone {
  return tier === "boom" ? "success" : tier === "bust" ? "warning" : undefined;
}
