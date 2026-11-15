import React from 'react';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { useThemeMode } from '../context/ThemeModeContext';
import { LINK_HIT_SLOP } from '../theme';

/**
 * The one "go to the full page" link of a compact module (UI pass 5 D6). A module either navigates (the whole row taps, trailing
 * arrow) or expands (chevron), never both in its header: the destination of an expandable module sits at the end of its expanded
 * body. Twin of web-next/src/components/ui/ModuleMore.tsx.
 */
export default function ModuleMore({ label, onPress }: { label: string; onPress: () => void }) {
  const { colors } = useThemeMode();
  return (
    <PressableScale accessibilityRole="link" accessibilityLabel={label} onPress={onPress} hitSlop={LINK_HIT_SLOP} style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}>
      <AppText style={{ fontSize: 14.5, fontWeight: '700', color: colors.accent }}>{`${label} →`}</AppText>
    </PressableScale>
  );
}
