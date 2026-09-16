import { createNavigationContainerRef } from '@react-navigation/native';

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
