import type { ThisWeek, ThisWeekRow } from './api';

type RowRoute = NonNullable<ThisWeekRow['route']>;
type NextRoute = NonNullable<ThisWeek['next_action']>['route'];

export type ThisWeekTarget =
  | { name: 'Matchup' | 'Waivers' | 'Trades' | 'DraftCenter'; params: { leagueId: string; leagueName: string } }
  | { name: 'Home'; params: { openAddLeague: true } };

/** Mobile screen for a "This week" CTA. There is no separate live-draft
 * screen on mobile, so a live draft opens the Draft Center. */
export function thisWeekTarget(route: RowRoute | NextRoute, leagueId: string, leagueName: string): ThisWeekTarget {
  const params = { leagueId, leagueName };
  switch (route) {
    case 'matchup':
      return { name: 'Matchup', params };
    case 'waivers':
      return { name: 'Waivers', params };
    case 'trade_hub':
      return { name: 'Trades', params };
    case 'draft_center':
    case 'live_draft':
      return { name: 'DraftCenter', params };
    case 'connect_league':
      return { name: 'Home', params: { openAddLeague: true } };
  }
}

export type ThisWeekColorKey = 'success' | 'danger' | 'accent' | 'textTertiary';

export function thisWeekToneKey(tone: ThisWeekRow['tone']): ThisWeekColorKey {
  switch (tone) {
    case 'positive':
      return 'success';
    case 'risk':
      return 'danger';
    case 'waiver':
    case 'trade':
      return 'accent';
    default:
      return 'textTertiary';
  }
}

/** Section title, with the week when the server knows it. */
export function thisWeekTitle(data: ThisWeek): string {
  return data.week ? `This week · Week ${data.week}` : 'This week';
}

/** True when there is something real to render (never an empty card). */
export function hasThisWeekContent(data: ThisWeek | null | undefined): data is ThisWeek {
  return Boolean(data && (data.next_action || data.rows.length > 0));
}

/** Headline of the trade idea the "This week" trade row already shows (an
 * 'Idea' row, not a hold), so the Top Priority hero can skip the same idea. */
export function thisWeekTradeIdeaHeadline(data: ThisWeek | null | undefined): string {
  const row = data?.rows?.find((candidate) => candidate.key === 'trade' && candidate.status === 'Idea');
  return row?.headline?.trim() ?? '';
}
