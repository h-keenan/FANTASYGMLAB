/**
 * "What FantasyDesk can do" (app). Web twin: web-next/src/lib/featureCatalog.ts
 * (same ids, order, names and copy; a web test pins that, and the tests here
 * pin the screen names and the GM orb icons). Pure data, no react-native
 * imports, so it runs under node:test.
 *
 * `route` is a RootStackParamList screen (checked against RootNavigator.tsx).
 * `icon` / `color` repeat what the same destination uses in GmOrb.tsx (checked
 * by the tests). `pro` mirrors a real server gate; `extra` is a note for
 * free features with a Pro part.
 */
export type FeatureGroupId = 'trade' | 'lineup' | 'pickup' | 'scout' | 'league' | 'keepup';

export type FeatureColorKey = 'accent' | 'danger' | 'success' | 'violet' | 'premium';

export const FEATURE_GROUPS: ReadonlyArray<{ id: FeatureGroupId; title: string }> = [
  { id: 'trade', title: 'Trade' },
  { id: 'lineup', title: 'Set your lineup' },
  { id: 'pickup', title: 'Pick up players' },
  { id: 'scout', title: 'Scout and research' },
  { id: 'league', title: 'Run your league' },
  { id: 'keepup', title: 'Keep up' },
];

export interface FeatureItem {
  id: string;
  group: FeatureGroupId;
  name: string;
  line: string;
  pro?: boolean;
  extra?: string;
  route: string;
  /** Extra route params (Trades tab). */
  tab?: 'block' | 'search' | 'make';
  /** Needs leagueId + leagueName; otherwise opens with no params. */
  leagueScoped: boolean;
  icon: string;
  color: FeatureColorKey;
}

// One item per line: the web test reads `id`, `name` and `pro` from each line.
/* prettier-ignore */
export const FEATURE_ITEMS: readonly FeatureItem[] = [
  { id: 'trade-analyzer', group: 'trade', name: 'Trade Analyzer', line: 'Grade any deal against your lineup before you send it.', route: 'Trades', tab: 'make', leagueScoped: true, icon: 'shuffle-outline', color: 'premium' },
  { id: 'trade-hub', group: 'trade', name: 'Trade ideas', line: 'Offers built for your roster and what each manager needs.', extra: 'Free shows a few ideas; Pro shows them all.', route: 'Trades', tab: 'block', leagueScoped: true, icon: 'shuffle-outline', color: 'premium' },
  { id: 'trade-finder', group: 'trade', name: 'Trade Finder', line: 'Shop your players and picks and see what partners could pay.', pro: true, route: 'Trades', tab: 'search', leagueScoped: true, icon: 'shuffle-outline', color: 'premium' },
  { id: 'trade-history', group: 'trade', name: 'Trade History', line: 'Trades you confirmed, and how they worked out.', route: 'TradeHistory', leagueScoped: false, icon: 'time-outline', color: 'violet' },
  { id: 'community', group: 'trade', name: 'Community', line: 'Trades other users chose to share, anonymized.', route: 'Community', leagueScoped: false, icon: 'people-circle-outline', color: 'premium' },

  { id: 'my-team', group: 'lineup', name: 'My Team', line: 'Your roster, lineup, strengths and needs.', route: 'MyTeam', leagueScoped: true, icon: 'shirt-outline', color: 'success' },
  { id: 'matchup', group: 'lineup', name: 'Matchup', line: "This week's win odds and any swap worth making.", route: 'Matchup', leagueScoped: true, icon: 'american-football-outline', color: 'success' },
  { id: 'gm-plan', group: 'lineup', name: 'GM Plan', line: 'Set rebuilding, competing or balanced and get a roadmap.', extra: 'Pro adds focus areas.', route: 'GmPlan', leagueScoped: true, icon: 'map-outline', color: 'premium' },

  { id: 'waivers', group: 'pickup', name: 'Waivers', line: 'Ranked pickups for your roster, with FAAB bid guidance.', extra: 'Pro adds the FAAB shortlist and usage stats.', route: 'Waivers', leagueScoped: true, icon: 'swap-horizontal-outline', color: 'success' },
  { id: 'draft-center', group: 'pickup', name: 'Draft Center', line: 'Your picks, draft order and draft-day decisions.', pro: true, route: 'DraftCenter', leagueScoped: true, icon: 'albums-outline', color: 'premium' },
  { id: 'live-draft', group: 'pickup', name: 'Live Draft', line: 'Pick recommendations while your Sleeper draft is running.', pro: true, route: 'LiveDraft', leagueScoped: true, icon: 'timer-outline', color: 'premium' },

  { id: 'players', group: 'scout', name: 'Players', line: 'Search any player for value, stats, trends and news.', route: 'Players', leagueScoped: true, icon: 'people-outline', color: 'violet' },
  { id: 'college-scouting', group: 'scout', name: 'College Scouting', line: 'Grade incoming prospects and keep a watchlist.', pro: true, route: 'CollegeProspects', leagueScoped: false, icon: 'school-outline', color: 'accent' },
  { id: 'league-rankings', group: 'scout', name: 'League Rankings', line: 'Power rankings for every team in your league.', route: 'Teams', leagueScoped: true, icon: 'people-circle-outline', color: 'violet' },

  { id: 'commissioner', group: 'league', name: 'Commissioner', line: 'League integrity: lineups, tanking signals, trades.', pro: true, route: 'Commissioner', leagueScoped: true, icon: 'shield-checkmark-outline', color: 'violet' },
  { id: 'playoff-odds', group: 'league', name: 'Playoff Odds', line: "Every team's chance at the playoffs.", pro: true, route: 'PlayoffOdds', leagueScoped: true, icon: 'podium-outline', color: 'violet' },
  { id: 'games', group: 'league', name: 'Games', line: "Season simulator and weekly pick'em.", route: 'Games', leagueScoped: true, icon: 'dice-outline', color: 'violet' },
  { id: 'league-recaps', group: 'league', name: 'League Recaps', line: "Your league's weekly recap and stories.", route: 'Recap', leagueScoped: true, icon: 'newspaper-outline', color: 'violet' },

  { id: 'dashboard', group: 'keepup', name: 'Dashboard', line: 'Your game plan and top moves for this week.', route: 'Dashboard', leagueScoped: true, icon: 'flash-outline', color: 'accent' },
  { id: 'alerts', group: 'keepup', name: 'Alerts', line: 'Injuries, news and updates on your players.', route: 'Alerts', leagueScoped: true, icon: 'notifications-outline', color: 'danger' },
  { id: 'news', group: 'keepup', name: 'News', line: 'The latest NFL news.', route: 'News', leagueScoped: false, icon: 'globe-outline', color: 'violet' },
  { id: 'portfolio', group: 'keepup', name: 'Portfolio', line: 'Your standing across every saved league.', pro: true, route: 'Portfolio', leagueScoped: false, icon: 'layers-outline', color: 'violet' },
];

export interface FeatureLeague {
  leagueId: string;
  leagueName: string;
}

export interface FeatureTarget {
  name: string;
  params: object | undefined;
}

/** Where an item opens, or null when it needs a league and none is known. */
export function featureTarget(item: FeatureItem, league: FeatureLeague | null): FeatureTarget | null {
  if (!item.leagueScoped) return { name: item.route, params: undefined };
  if (!league) return null;
  return { name: item.route, params: item.tab ? { ...league, initialTab: item.tab } : { ...league } };
}
