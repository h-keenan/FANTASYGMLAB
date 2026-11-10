import type { DashboardItem } from './api';

export type WatchTagKind = 'trending' | 'injury' | 'waiver' | 'other';

/**
 * The real usage-drop percentage a Value Trend item carries. The backend
 * (modules.dashboard_engine.build_value_trend_tile) writes it into the
 * item's note as "Usage down 37% (high confidence) ...". There is no weekly
 * series on the payload, so the dashboard shows this one number and never
 * draws a sparkline. Null when the item has no such figure: nothing is
 * rendered in that case.
 */
export function usageTrendPct(item: Pick<DashboardItem, 'reason'> & { supporting_context?: string | null }): number | null {
  const match = /usage down (\d+(?:\.\d+)?)%/i.exec(`${item.reason ?? ''} ${item.supporting_context ?? ''}`);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

/** Which TRENDING / INJURY / WAIVER tag a Watchlist & Alerts row gets. */
export function watchTagKind(
  item: Pick<DashboardItem, 'category' | 'headline' | 'reason'> & {
    route_player_injury_status?: string | null;
    supporting_context?: string | null;
  },
): WatchTagKind {
  if (item.category === 'waiver_opportunity') return 'waiver';
  if (usageTrendPct(item) !== null || /trend/i.test(item.headline)) return 'trending';
  if (item.route_player_injury_status || /injur/i.test(`${item.headline} ${item.reason}`)) return 'injury';
  return 'other';
}

export const WATCH_TAG_LABEL: Record<WatchTagKind, string | null> = {
  trending: 'Trending',
  injury: 'Injury',
  waiver: 'Waiver',
  other: null,
};

const NON_TERMINAL = /^(?:[A-Z]|Jr|Sr|II|III|IV|St|vs)\.$/;

/**
 * The first sentence of a feed string, with any " | " tail dropped and name
 * suffixes (Jr., II.) and initials not treated as sentence ends. Capped so a
 * row summary never runs away. Mirrors web lib/dashboardPresentation.ts.
 */
export function firstSentence(text: string | null | undefined, max = 140): string {
  const head = (text ?? '').split(/\s\|\s/)[0].replace(/\s+/g, ' ').trim();
  const re = /[.!?](?=\s|$)/g;
  let end = head.length;
  let match: RegExpExecArray | null;
  while ((match = re.exec(head))) {
    const token = head.slice(0, match.index + 1).split(' ').pop() ?? '';
    if (NON_TERMINAL.test(token)) continue;
    end = match.index + 1;
    break;
  }
  const out = head.slice(0, end);
  return out.length > max ? `${out.slice(0, max - 1).trimEnd()}…` : out;
}

/** One clean sentence for a Watchlist row: from structured fields when there are any, else the first sentence. */
export function watchSummary(
  item: Pick<DashboardItem, 'reason'> & { supporting_context?: string | null; route_player_injury_status?: string | null },
): string {
  const pct = usageTrendPct(item);
  if (pct !== null) return `Usage is down ${pct}% recently.`;
  const status = (item.route_player_injury_status ?? '').trim();
  if (status) return `Listed as ${status}; check your lineup.`;
  return firstSentence(item.reason);
}

/** Row title when the item names no player: its headline, never a bare position code. */
export function watchTitle(item: Pick<DashboardItem, 'headline'>): string {
  const headline = (item.headline ?? '').trim();
  return /^[A-Z]{1,3}$/.test(headline) ? `${headline} room` : headline;
}
