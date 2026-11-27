/**
 * Deep links for the no-signup "try" ad links: fantasygmlab://try/<topic> (web twin: /try/<topic>,
 * web-next/src/lib/tryLinks.ts). Pure so it can be tested; RootNavigator wires it to Linking.
 *
 * The app has ONE no-account demo surface, the Sample league (SampleLeagueScreen; reachable signed out). So the
 * topics that have a matching sample view open it on that tab:
 *   trade      -> Trade tab (sample offer + verdict)
 *   start-sit  -> Top moves tab (sample lineup/roster moves)
 *   waivers    -> Top moves tab (sample add/watch move)
 * `playoffs` and `dynasty-values` have no demo view in the app (the playoff schedule and the value chart are web
 * pages), so they are NOT claimed by this handler and the link is left to the web page.
 * The app captures no UTMs and sends no demo analytics, so nothing campaign-related is parsed here.
 */
import type { SampleTab } from './sampleLeague';

export type TryTopic = 'start-sit' | 'trade' | 'waivers' | 'playoffs' | 'dynasty-values';

export const TRY_TOPIC_TAB: Partial<Record<TryTopic, SampleTab>> = {
  'start-sit': 'game_plan',
  trade: 'trade',
  waivers: 'game_plan',
};

/** The sample-league tab a fantasygmlab://try/<topic> URL should open, or null when it is not a supported try link. */
export function tryTabFromUrl(url: string | null | undefined): SampleTab | null {
  if (!url) return null;
  const match = /^[a-z][a-z0-9+.-]*:\/\/\/?([^?#]*)/i.exec(url.trim());
  if (!match) return null;
  const parts = match[1].replace(/\/+$/, '').split('/');
  if (parts.length !== 2 || parts[0] !== 'try') return null;
  return TRY_TOPIC_TAB[parts[1] as TryTopic] ?? null;
}
