/**
 * The My Team roster basis, one definition for web and app (byte-identical lib twin).
 *
 * coridian_, 2026-10-18: "the bench should be in order so. QBs, RBs, WRs, TEs, K, DST". The API returns bench players in
 * value order; the sort is stable, so value order holds inside each position group. Unknown positions sort last.
 *
 * Best ball (Sleeper settings.best_ball): Sleeper sets the lineup itself from the highest weekly scorers, so there is no
 * suggested starters/bench split. The basis is one position-ordered roster (starters + active bench) with the optimizer's
 * suggested slot labels stripped; IR and taxi stay their own groups.
 */

const POSITION_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF", "DST"];

export function rosterPositionIndex(position: string | null | undefined): number {
  const index = POSITION_ORDER.indexOf((position || "").toUpperCase());
  return index === -1 ? POSITION_ORDER.length : index;
}

export interface RosterBasisPlayer {
  position: string | null;
  slot: string | null;
  roster_slot?: "starter" | "bench" | "ir" | "taxi";
}

export interface RosterBasis<T extends RosterBasisPlayer> {
  /** The suggested starters (unchanged order); for best ball they are folded into `activeBench`. */
  starters: T[];
  /** Active bench, position-ordered. For best ball: the whole active roster (starters + bench), slot labels stripped. */
  activeBench: T[];
  irBench: T[];
  taxiBench: T[];
}

export function sortByRosterPosition<T extends RosterBasisPlayer>(list: readonly T[]): T[] {
  return [...list].sort((a, b) => rosterPositionIndex(a.position) - rosterPositionIndex(b.position));
}

export function buildRosterBasis<T extends RosterBasisPlayer>(starters: readonly T[], bench: readonly T[], bestBall: boolean): RosterBasis<T> {
  const active = bench.filter((p) => p.roster_slot !== "ir" && p.roster_slot !== "taxi");
  const activeBench = bestBall
    ? sortByRosterPosition([...starters, ...active].map((p) => ({ ...p, slot: null })))
    : sortByRosterPosition(active);
  return {
    starters: [...starters],
    activeBench,
    irBench: sortByRosterPosition(bench.filter((p) => p.roster_slot === "ir")),
    taxiBench: sortByRosterPosition(bench.filter((p) => p.roster_slot === "taxi")),
  };
}
