import { createNavigationContainerRef } from '@react-navigation/native';
import { StackActions } from '@react-navigation/routers';

import { leagueSwitchDestination, type LeagueTarget } from '../lib/leagueSwitch';

import type { RootStackParamList } from './RootNavigator';

/**
 * A ref-based handle onto the navigator so components rendered outside the
 * screen tree (the GM Orb floating menu) can navigate and read the current
 * route's params without every screen threading navigation/league context
 * down manually.
 */
export const navigationRef = createNavigationContainerRef<RootStackParamList>();

export function currentLeagueContext(): { leagueId: string; leagueName: string } | null {
  if (!navigationRef.isReady()) return null;
  const route = navigationRef.getCurrentRoute();
  const params = route?.params as { leagueId?: string; leagueName?: string } | undefined;
  if (params?.leagueId && params?.leagueName) {
    return { leagueId: params.leagueId, leagueName: params.leagueName };
  }
  return null;
}

/**
 * Switch to another saved league, staying on the current screen when it's
 * league-scoped (tap-depth audit #5, mirrors web's swapLeagueIdInPath) —
 * `replace`, so the stack doesn't grow — and otherwise going to the new
 * league's Dashboard (My Team for ESPN) via `popTo`. Shared by the header
 * league switcher and the GM orb's inline list.
 */
export function switchLeagueKeepingScreen(target: LeagueTarget, currentLeagueId: string | null | undefined): void {
  if (!navigationRef.isReady()) return;
  const current = navigationRef.getCurrentRoute();
  const destination = leagueSwitchDestination(current, currentLeagueId, target);
  if (current && destination.name === current.name) {
    navigationRef.dispatch(StackActions.replace(destination.name, destination.params));
  } else {
    navigationRef.dispatch(StackActions.popTo(destination.name, destination.params));
  }
}
