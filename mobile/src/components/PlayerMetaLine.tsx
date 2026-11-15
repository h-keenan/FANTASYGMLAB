import React, { useMemo, useState, type ReactNode } from 'react';
import { PixelRatio, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Money from './Money';
import { useThemeMode } from '../context/ThemeModeContext';
import type { FactTone } from '../lib/playerAnatomy';
import { fitMetaParts, type MetaPart } from '../lib/playerMetaFit';
import type { ThemeColors } from '../theme';

function toneColor(tone: string | undefined, colors: ThemeColors): string | undefined {
  switch (tone as FactTone | undefined) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    case 'muted': return colors.textTertiary;
    default: return undefined;
  }
}

/**
 * THE sub-line under a player name, native twin of web-next/src/components/ui/PlayerMetaLine.tsx: parts leave by the ladder in
 * lib/playerMetaFit.ts (Age, then team, then a bye that is not soon) when the width is short, the projection / status never
 * leave, and what is left wraps instead of being cut (no numberOfLines / ellipsis). `trailing` (the grade tile) is beside it.
 */
export default function PlayerMetaLine({ parts, trailing, testID = 'row-meta' }: { parts: readonly MetaPart[]; trailing?: ReactNode; testID?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [width, setWidth] = useState<number | null>(null);
  const shown = fitMetaParts(parts, width, 12 * Math.min(PixelRatio.getFontScale(), 1.6));
  return (
    <View style={styles.row} testID={testID}>
      <View style={styles.parts} onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
        {shown.map((part, i) => (
          <AppText key={part.key} style={[styles.meta, part.tone ? { color: toneColor(part.tone, colors) } : null, part.tone === 'warning' || part.key === 'proj' ? { fontWeight: '700' } : null]}>
            <Money>{part.text}</Money>
            {i < shown.length - 1 ? <AppText style={styles.meta}>{' ·'}</AppText> : null}
          </AppText>
        ))}
      </View>
      {trailing}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'flex-start', gap: 6 },
    parts: { flex: 1, minWidth: 0, flexDirection: 'row', flexWrap: 'wrap', columnGap: 4 },
    meta: { fontSize: 12, color: colors.textTertiary, flexShrink: 0 },
  });
}
