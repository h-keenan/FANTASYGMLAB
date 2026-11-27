import React from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ConnectPlatformKey } from '../lib/connectFlow';

/**
 * A league platform's monogram badge: a rounded square in the platform's brand color with its initial. Shared by the
 * connect tiles and the stepper headers. Colors are theme tokens (platform*), no logo files. Web twin:
 * web-next/src/components/PlatformBadge.tsx.
 */
export default function PlatformBadge({ platform, size = 40 }: { platform: ConnectPlatformKey; size?: number }) {
  const { colors } = useThemeMode();
  const map: Record<ConnectPlatformKey, { letter: string; color: string }> = {
    sleeper: { letter: 'S', color: colors.platformSleeper },
    yahoo: { letter: 'Y', color: colors.platformYahoo },
    espn: { letter: 'E', color: colors.platformEspn },
    fleaflicker: { letter: 'F', color: colors.platformFleaflicker },
    mfl: { letter: 'M', color: colors.platformMfl },
  };
  const { letter, color } = map[platform];
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      testID={`platform-badge-${platform}`}
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.3), backgroundColor: color, alignItems: 'center', justifyContent: 'center' }}
    >
      <AppText style={{ color: colors.onPlatform, fontSize: Math.round(size * 0.46), fontWeight: '800' }}>{letter}</AppText>
    </View>
  );
}
