import React, { useMemo, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactPlayerCard from './CompactPlayerCard';
import { useThemeMode } from '../context/ThemeModeContext';
import type { PlayerRef } from '../lib/playerAnatomy';
import { spacing, type ThemeColors } from '../theme';

/**
 * Bar row (waivers add row, standings, rankings): a mini bar showing a value as a 0..1 `fraction` of the largest in
 * the list, the player (through CompactPlayerCard, avatar included) or a team on the left, ONE trailing number.
 * Twin of web ui/RankRow.tsx.
 */
export default function RankRow({
  player,
  title,
  leading,
  detail,
  fraction,
  trailing,
  barLabel,
  rank,
  onPress,
  testID = 'rank-row',
}: {
  player?: PlayerRef;
  title?: string;
  leading?: ReactNode;
  detail?: string | null;
  fraction: number;
  trailing: ReactNode;
  barLabel?: string;
  rank?: number | null;
  onPress?: () => void;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const pct = Math.round(Math.max(0, Math.min(1, fraction)) * 100);
  const body = (
    <View style={styles.wrap} testID={testID}>
      <View style={styles.top}>
        {rank != null ? <AppText style={styles.rank}>{rank}</AppText> : null}
        <View style={styles.main}>
          {player ? (
            <CompactPlayerCard player={player} detail={detail} trailing={<AppText style={styles.value}>{trailing}</AppText>} />
          ) : (
            <View style={styles.teamRow}>
              {leading}
              <View style={styles.main}>
                <AppText style={styles.title}>{title}</AppText>
                {detail ? <AppText style={styles.detail}>{detail}</AppText> : null}
              </View>
              <AppText style={styles.value}>{trailing}</AppText>
            </View>
          )}
        </View>
      </View>
      <View style={styles.track} accessibilityLabel={barLabel ?? `${pct}% of the top`}>
        <View style={[styles.fill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
  return onPress ? (
    <Pressable accessibilityRole="button" onPress={onPress}>{body}</Pressable>
  ) : (
    body
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: 4, paddingVertical: 2 },
    top: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    rank: { width: 20, fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    main: { flex: 1, minWidth: 0 },
    teamRow: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    title: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    detail: { fontSize: 12, color: colors.textTertiary },
    value: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    track: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.1)', overflow: 'hidden' },
    fill: { height: 6, borderRadius: 3, backgroundColor: colors.accentStrong },
  });
}
