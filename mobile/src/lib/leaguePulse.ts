/**
 * League Pulse ("League Activity") highlights, mirroring web-next's
 * LeaguePulseCard.leaguePulseHighlights exactly: Most Active Manager, Hot
 * Streak, Cold Streak, each only when real data supports it (never
 * fabricated). Pure (no React) so `npm test` can run it directly.
 */

export interface PulseTeam {
  team_name?: string | null;
  avatar_url?: string | null;
  transaction_activity_count?: number | null;
  current_streak?: number | null;
}

export type PulseTone = 'positive' | 'negative' | 'neutral';

export interface PulseHighlight<T extends PulseTeam = PulseTeam> {
  key: 'most-active' | 'hot-streak' | 'cold-streak';
  label: string;
  tone: PulseTone;
  team: T;
  metric: string;
}

function mostActive<T extends PulseTeam>(teams: T[]): PulseHighlight<T> | null {
  if (teams.length === 0) return null;
  const leader = teams.reduce((best, team) =>
    (team.transaction_activity_count ?? 0) > (best.transaction_activity_count ?? 0) ? team : best,
  );
  const count = leader.transaction_activity_count ?? 0;
  if (count <= 0) return null;
  return { key: 'most-active', label: 'Most Active Manager', tone: 'neutral', team: leader, metric: `${count} move${count === 1 ? '' : 's'}` };
}

function hotStreak<T extends PulseTeam>(teams: T[]): PulseHighlight<T> | null {
  const candidates = teams.filter((t) => (t.current_streak ?? 0) >= 2);
  if (candidates.length === 0) return null;
  const leader = candidates.reduce((best, t) => ((t.current_streak ?? 0) > (best.current_streak ?? 0) ? t : best));
  return { key: 'hot-streak', label: 'Hot Streak', tone: 'positive', team: leader, metric: `W${leader.current_streak}` };
}

function coldStreak<T extends PulseTeam>(teams: T[]): PulseHighlight<T> | null {
  const candidates = teams.filter((t) => (t.current_streak ?? 0) <= -2);
  if (candidates.length === 0) return null;
  const leader = candidates.reduce((worst, t) => ((t.current_streak ?? 0) < (worst.current_streak ?? 0) ? t : worst));
  return { key: 'cold-streak', label: 'Cold Streak', tone: 'negative', team: leader, metric: `L${Math.abs(leader.current_streak ?? 0)}` };
}

export function leaguePulseHighlights<T extends PulseTeam>(teams: T[]): PulseHighlight<T>[] {
  return [mostActive(teams), hotStreak(teams), coldStreak(teams)].filter((h): h is PulseHighlight<T> => h !== null);
}
