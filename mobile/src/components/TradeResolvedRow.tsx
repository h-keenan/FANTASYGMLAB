import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { SuccessCheck } from './Motion';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing } from '../theme';

/**
 * What a trade card collapses into once it is answered (motion audit candidate 3): a single row with the
 * `SuccessCheck` for an accepted trade or a muted cross for a declined one. Twin of web ui/TradeResolvedRow.tsx.
 */
export default function TradeResolvedRow({ kind, label, testID = 'trade-resolved' }: { kind: 'accepted' | 'declined'; label: string; testID?: string }) {
  const { colors } = useThemeMode();
  return (
    <View style={styles.row} testID={testID} accessibilityRole="text" accessibilityLiveRegion="polite">
      {kind === 'accepted' ? <SuccessCheck size={24} label="Trade done" /> : <Ionicons name="close-circle-outline" size={24} color={colors.textTertiary} />}
      <AppText style={[styles.label, { color: kind === 'accepted' ? colors.success : colors.textSecondary }]}>{label}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: 4 },
  label: { fontSize: 14, fontWeight: '800' },
});
