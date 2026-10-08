/**
 * "All leagues at a glance" (My Leagues screen) — the response types for
 * GET /v1/leagues-glance (services/mobile_api_service.py, built per league
 * by modules/league_glance.py) plus the pure presentation decisions the
 * section makes: whether it is shown, locked, or active; whether the cards
 * render as a 2-column grid or a vertical stack; and the compact labels.
 *
 * Kept free of React/React Native imports so `npm test` (node's own test
 * runner with --experimental-strip-types) can exercise it directly.
 */

export interface LeagueGlanceRecord {
  wins: number;
  losses: number;
  ties: number;
  record_label: string;
  /** Null until real games exist (an 0-0 "rank" would be meaningless). */
  standing_rank: number | null;
  team_count: number;
  playoff_status: string;
  standings_available: boolean;
}

export interface LeagueGlanceWaiver {
  player_id: string;
  name: string;
  position: string;
  team: string;
  /** One-line reason, the same text the Dashboard's waiver tile uses. */
  reason: string;
}

export interface LeagueGlanceTrade {
  headline: string;
  partner_team_name: string;
}

export interface LeagueGlanceNews {
  /** Roster-relevant news items, same feed the league's Alerts screen lists. */
  news_count: number;
  /** Rostered players carrying an injury designation. */
  injury_count: number;
}

export interface LeagueGlanceNeed {
  category: string;
  label: string;
  value: string;
  tier_label: string;
}

export interface LeagueGlance {
  league_id: string;
  league_name: string;
  team_name: string;
  record: LeagueGlanceRecord | null;
  waiver: LeagueGlanceWaiver | null;
  trade: LeagueGlanceTrade | null;
  news: LeagueGlanceNews;
  need: LeagueGlanceNeed | null;
}

export interface LeagueGlanceFailedLeague {
  league_id: string;
  league_name: string;
  reason: string;
}

export interface LeaguesGlanceResponse {
  ok: true;
  is_premium: boolean;
  lens: string;
  leagues: LeagueGlance[];
  failed_leagues: LeagueGlanceFailedLeague[];
  upsell: { title: string; body: string } | null;
  cache_ttl_seconds: number;
}

/** hidden: nothing to show (unknown plan, no leagues, or a single Premium
 * league with nothing to compare). locked: Free teaser + upgrade CTA.
 * active: fetch and render real cards. */
export type GlanceSectionState = 'hidden' | 'locked' | 'active';

export function glanceSectionState(input: {
  entitlement: string | null | undefined;
  profileStatus: string | null | undefined;
  savedLeagueCount: number;
}): GlanceSectionState {
  // Same rule HomeScreen's league-cap lock follows: an unverified plan is
  // never shown as Free, so a paying user never sees a lock over a blip.
  if (input.profileStatus !== 'ok' || !input.entitlement) return 'hidden';
  if (input.savedLeagueCount <= 0) return 'hidden';
  if (input.entitlement !== 'premium') return 'locked';
  return input.savedLeagueCount >= 2 ? 'active' : 'hidden';
}

export type GlanceLayout = 'grid' | 'stack';

/** Exactly two cards sit side by side in a 2-column grid; any other count
 * (one surviving card, or three and up) stacks vertically. */
export function glanceLayout(cardCount: number): GlanceLayout {
  return cardCount === 2 ? 'grid' : 'stack';
}

export function ordinal(value: number): string {
  const mod100 = value % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${value}th`;
  switch (value % 10) {
    case 1:
      return `${value}st`;
    case 2:
      return `${value}nd`;
    case 3:
      return `${value}rd`;
    default:
      return `${value}th`;
  }
}

/** "6-2" plus "1st of 12" once standings are real. */
export function glanceRecordParts(record: LeagueGlanceRecord | null): { record: string; rank: string } {
  if (!record) return { record: '', rank: '' };
  const recordText = record.record_label || `${record.wins}-${record.losses}${record.ties ? `-${record.ties}` : ''}`;
  const rank =
    record.standing_rank != null && record.team_count > 0
      ? `${ordinal(record.standing_rank)} of ${record.team_count}`
      : '';
  return { record: recordText, rank };
}

/** The news/injury count badge. `tone` is "risk" whenever an injury is in
 * the count (red is reserved for injury/risk), otherwise neutral. */
export function glanceNewsBadge(news: LeagueGlanceNews | null | undefined): {
  count: number;
  tone: 'risk' | 'neutral';
  accessibilityLabel: string;
} {
  const newsCount = Math.max(0, news?.news_count ?? 0);
  const injuryCount = Math.max(0, news?.injury_count ?? 0);
  const parts = [
    `${newsCount} news ${newsCount === 1 ? 'item' : 'items'}`,
    `${injuryCount} injured ${injuryCount === 1 ? 'player' : 'players'}`,
  ];
  return {
    count: newsCount + injuryCount,
    tone: injuryCount > 0 ? 'risk' : 'neutral',
    accessibilityLabel: `${parts.join(', ')}. Opens league alerts.`,
  };
}

export function glanceWaiverHeadline(waiver: LeagueGlanceWaiver): string {
  const meta = [waiver.position, waiver.team].filter(Boolean).join(' · ');
  return meta ? `${waiver.name} · ${meta}` : waiver.name;
}

/** Each module on a card opens that specific feature for that league
 * rather than the league's generic Dashboard. */
export type GlanceModule = 'record' | 'waiver' | 'trade' | 'news' | 'need';

export type GlanceDestination =
  | { screen: 'Dashboard' }
  | { screen: 'Waivers' }
  | { screen: 'Trades'; initialTab: 'block' }
  | { screen: 'Alerts' }
  | { screen: 'MyTeam' };

export function glanceDestination(module: GlanceModule): GlanceDestination {
  switch (module) {
    case 'waiver':
      return { screen: 'Waivers' };
    case 'trade':
      return { screen: 'Trades', initialTab: 'block' };
    case 'news':
      return { screen: 'Alerts' };
    case 'need':
      return { screen: 'MyTeam' };
    case 'record':
    default:
      return { screen: 'Dashboard' };
  }
}

/** "Couldn't load 2 leagues right now: A, B." */
export function glanceFailedNote(failed: LeagueGlanceFailedLeague[]): string {
  if (failed.length === 0) return '';
  const names = failed.map((league) => league.league_name).join(', ');
  return `Couldn't load ${failed.length} ${failed.length === 1 ? 'league' : 'leagues'} right now: ${names}.`;
}
