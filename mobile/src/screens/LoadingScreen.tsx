import React from 'react';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { SkeletonPage, type SkeletonLayout } from '../components/Skeleton';
import { useThemeMode } from '../context/ThemeModeContext';
import type { PageTabFamilyKey } from '../lib/pageFamilies';

/**
 * Cold-start / auth-check loading state: a content-shaped skeleton of the screen that is about to appear (header,
 * optional family tab strip, then the layout for its family), never a splash with a "Loading..." line. `label` is the
 * screen's name and becomes the one screen-reader status ("Loading your leagues"). Web twin:
 * web-next/src/components/LoadingScreen.tsx; the pieces live in components/Skeleton.tsx.
 */
export default function LoadingScreen({ label = 'your leagues', layout = 'dashboard', family, onRetry }: { label?: string; layout?: SkeletonLayout; family?: PageTabFamilyKey; onRetry?: () => void }) {
  const { colors } = useThemeMode();
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <SkeletonPage label={label} layout={layout} family={family} topInset={insets.top} onRetry={onRetry} />
    </View>
  );
}
