/**
 * My Team's Team Analysis rows and Roster Composition split. Mirrors
 * web-next/src/lib/myTeamAnalysis.ts (and the room-outlook labels in
 * web-next/src/lib/myTeamPresentation.ts). Statuses come from
 * GET .../my-team-needs; composition comes from each player's own `score`.
 */

export type AnalysisTone = 'success' | 'warning' | 'danger' | 'information';

export interface TeamAnalysisRow {
  position: string;
  status: string;
  tone: AnalysisTone;
  /** Full sentence, shown only when the row is expanded. */
  body: string;
}

interface NeedGroup {
  position: string;
  classification: string;
  reasons: string[];
  upgrade_opportunity: boolean;
  temporary_injury_pressure: boolean;
}

const ORDER = ['QB', 'RB', 'WR', 'TE'];

function statusFor(
  group: NeedGroup,
  strengths: Set<string>,
): { status: string; tone: AnalysisTone } {
  if (strengths.has(group.position)) return { status: 'Strength', tone: 'success' };
  const kind = (group.classification || '').trim().toLowerCase();
  if (kind === 'short_term_need') return { status: 'Thin', tone: 'danger' };
  if (kind === 'future_risk') return { status: 'Future risk', tone: 'danger' };
  if (group.upgrade_opportunity) return { status: 'Upgrade opportunity', tone: 'warning' };
  if (group.temporary_injury_pressure) return { status: 'Injury pressure', tone: 'warning' };
  return { status: 'Covered', tone: 'information' };
}

/** One row per position room, QB/RB/WR/TE first. */
export function buildTeamAnalysisRows(needs: {
  strengths: string[];
  position_groups: NeedGroup[];
}): TeamAnalysisRow[] {
  const strengths = new Set(needs.strengths.map((s) => s.toUpperCase()));
  const rank = (position: string) => {
    const index = ORDER.indexOf(position);
    return index === -1 ? ORDER.length : index;
  };
  return needs.position_groups
    .map((group) => ({ ...group, position: (group.position || '').toUpperCase() }))
    .filter((group) => group.position)
    .map((group) => ({
      position: group.position,
      ...statusFor(group, strengths),
      body: group.reasons[0] || 'Existing coverage assessment.',
    }))
    .sort((a, b) => rank(a.position) - rank(b.position));
}

export interface CompositionSegment {
  key: string;
  label: string;
  value: number;
  /** Whole-number percent; segments always add to exactly 100. */
  percent: number;
}

/** Value split across roster groups; empty groups are dropped. Largest-remainder rounding. */
export function buildRosterComposition(
  groups: { key: string; label: string; players: { score: number | null }[] }[],
): CompositionSegment[] {
  const sized = groups
    .map((group) => ({
      key: group.key,
      label: group.label,
      value: group.players.reduce((sum, p) => sum + (p.score ?? 0), 0),
    }))
    .filter((group) => group.value > 0);
  const total = sized.reduce((sum, group) => sum + group.value, 0);
  if (total <= 0) return [];
  const raw = sized.map((group) => (group.value / total) * 100);
  const percents = raw.map((r) => Math.floor(r));
  let remaining = 100 - percents.reduce((sum, p) => sum + p, 0);
  const byRemainder = raw
    .map((r, index) => ({ index, remainder: r - Math.floor(r) }))
    .sort((a, b) => b.remainder - a.remainder);
  for (const { index } of byRemainder) {
    if (remaining <= 0) break;
    percents[index] += 1;
    remaining -= 1;
  }
  return sized.map((group, index) => ({ ...group, percent: percents[index] }));
}
