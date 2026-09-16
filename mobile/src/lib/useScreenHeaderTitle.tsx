import React, { useEffect } from 'react';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import ScreenHeaderTitle from '../components/ScreenHeaderTitle';

/** Sets the two-line (screen + league) native-stack header title. See ScreenHeaderTitle. */
export function useScreenHeaderTitle(
  navigation: Pick<NativeStackNavigationProp<Record<string, object | undefined>>, 'setOptions'>,
  screen: string,
  league?: string,
) {
  useEffect(() => {
    navigation.setOptions({
      headerTitle: () => <ScreenHeaderTitle screen={screen} league={league} />,
    });
  }, [navigation, screen, league]);
}
