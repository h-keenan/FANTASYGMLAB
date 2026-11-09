import { ordinal } from './pickGroups.ts';

interface LensProspect {
  position: string;
  draft_year: number | null;
  aggregate: { avg_round_projection: number | null };
}
interface LensPick {
  season: number | null;
  round: number | null;
}
interface LensNeedGroup {
  position: string;
  classification: string;
}

/**
 * League-aware overlay for the Scouting tab. No scoring model of its own: it
 * only cross-references the prospect's existing community projected round and
 * position with data Draft Center already has (My Team's position-need
 * classification and the user's own pick slots). Mirrors web-next/src/lib/scoutingLens.ts.
 */
export interface ScoutingLens {
  /** Positions My Team flags as a short-term need or future risk. */
  needPositions: ReadonlySet<string>;
  /** The user's own picks. */
  myPicks: readonly LensPick[];
}

export interface ProspectFit {
  /** Position is one of the user's flagged need rooms. */
  needsPosition: boolean;
  /** 'Fits your 1st (2027)' when the community round projection lines up with a round the user holds in that class. */
  pickNote: string | null;
}

export function needPositionsFrom(groups: readonly LensNeedGroup[] | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const group of groups ?? []) {
    if (group.classification === 'short_term_need' || group.classification === 'future_risk') {
      out.add(group.position.toUpperCase());
    }
  }
  return out;
}

export function prospectFit(prospect: LensProspect, lens: ScoutingLens): ProspectFit {
  const needsPosition = lens.needPositions.has((prospect.position ?? '').toUpperCase());
  const projected = prospect.aggregate.avg_round_projection;
  let pickNote: string | null = null;
  if (projected != null && prospect.draft_year != null) {
    const round = Math.max(1, Math.round(projected));
    const hit = lens.myPicks.find((pick) => pick.season === prospect.draft_year && pick.round === round);
    if (hit) pickNote = `Fits your ${ordinal(round)} (${prospect.draft_year})`;
  }
  return { needsPosition, pickNote };
}

/** Stable re-rank for the league lens: need + pick fit first, then either, then the base order. */
export function rankByFit<P extends LensProspect>(prospects: P[], lens: ScoutingLens): P[] {
  const weight = (prospect: P) => {
    const fit = prospectFit(prospect, lens);
    return (fit.needsPosition ? 1 : 0) + (fit.pickNote ? 1 : 0);
  };
  return prospects
    .map((prospect, index) => ({ prospect, index, w: weight(prospect) }))
    .sort((a, b) => b.w - a.w || a.index - b.index)
    .map((entry) => entry.prospect);
}
