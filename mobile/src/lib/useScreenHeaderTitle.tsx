import React, { useEffect } from 'react';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import ScreenHeaderTitle from '../components/ScreenHeaderTitle';
import { headerTitleFor } from './appHeader';

/**
 * THE app header title: the two-line (screen + league) native-stack header title. See ScreenHeaderTitle. The in-content BrandHeaderBar
 * that used to stack a second header under it is gone (header rewrite phase 7); a screen's header actions go in its own `headerRight`.
 * Rule 1 (lib/appHeader.ts `headerTitleFor`): a tab page's name is the bottom pill's job, so its header shows the league only.
 */
export function useScreenHeaderTitle(
  navigation: Pick<NativeStackNavigationProp<Record<string, object | undefined>>, 'setOptions'>,
  screen: string,
  league?: string,
) {
  useEffect(() => {
    const shown = headerTitleFor(screen);
    navigation.setOptions({
      headerTitle: () => <ScreenHeaderTitle screen={shown} league={league} />,
    });
  }, [navigation, screen, league]);
}
