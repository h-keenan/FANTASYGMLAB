import React, { useEffect, useMemo, useRef } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { animateRowExpand } from './PlayerAccordionRow';
import { useThemeMode } from '../context/ThemeModeContext';
import type { FactTone, FairnessMeter } from '../lib/playerAnatomy';
import { spacing, type ThemeColors } from '../theme';

export function toneColor(tone: FactTone, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    default: return colors.textTertiary;
  }
}

/**
 * THE fairness meter row: a centre-anchored track, a fill from the centre to the marker, and the label. A live edit
 * glides the marker (layout animation; reduced motion snaps). Used by TradeCompactCard (read-only) and TradeScale (the
 * builder). Twin of web-next ui/FairnessMeterRow.tsx.
 */
export default function FairnessMeterRow({ meter, accessibilityLabel }: { meter: FairnessMeter; accessibilityLabel?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const last = useRef(meter.position);
  useEffect(() => {
    if (last.current !== meter.position) animateRowExpand();
    last.current = meter.position;
  }, [meter.position]);
  const color = toneColor(meter.tone, colors);
  return (
    <View style={styles.meterRow} testID="fairness-meter">
      <View style={styles.track} accessible accessibilityRole="image" accessibilityLabel={accessibilityLabel ?? meter.description}>
        <View style={[styles.fill, { left: `${Math.min(50, meter.position * 100)}%`, width: `${Math.abs(meter.position - 0.5) * 100}%`, backgroundColor: color }]} testID="fairness-fill" />
        <View style={styles.mid} />
        <View style={[styles.marker, { left: `${meter.position * 100}%`, backgroundColor: color, borderColor: colors.surfaceSolid }]} testID="fairness-marker" />
      </View>
      <AppText style={[styles.verdict, { color }]} testID="fairness-label" accessibilityLiveRegion="polite">{meter.label}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    track: { flex: 1, height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.12)', justifyContent: 'center' },
    fill: { position: 'absolute', top: 0, height: 8, borderRadius: 4, opacity: 0.55 },
    mid: { position: 'absolute', left: '50%', width: 2, height: 14, marginLeft: -1, backgroundColor: colors.textTertiary },
    marker: { position: 'absolute', width: 14, height: 14, borderRadius: 7, marginLeft: -7, borderWidth: 2 },
    verdict: { fontSize: 12, fontWeight: '800', flexShrink: 1, textAlign: 'right' },
  });
}
