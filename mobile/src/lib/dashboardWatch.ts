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
