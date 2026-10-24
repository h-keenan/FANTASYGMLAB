import React, { useEffect } from 'react';
import { View } from 'react-native';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from './BrandedSpinner';
import { resolveLegacyRedirect } from '../lib/homeRedirects';

/**
 * Screen component for a retired route (LeagueDetail, GmTargets, TeamStance).
 * Replaces itself with the route's new home so the old name still resolves
 * from deep links, push taps and persisted navigation state, without leaving
 * a dead screen in the back stack.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- screens have different param lists
export function createLegacyRedirectScreen(routeName: string): React.ComponentType<any> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function LegacyRedirect({ route, navigation }: any) {
    const headerHeight = useHeaderHeight();
    const params = (route?.params ?? {}) as { leagueId: string; leagueName: string };
    useEffect(() => {
      const target = resolveLegacyRedirect(routeName, params);
      if (target) navigation.replace(target.name, target.params);
      // Runs once per mount; the screen is replaced immediately.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    return (
      <View style={{ flex: 1, paddingTop: headerHeight }}>
        <BrandedSpinner />
      </View>
    );
  }
  LegacyRedirect.displayName = `LegacyRedirect(${routeName})`;
  return LegacyRedirect;
}
