import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { WaiverFaabGuidance } from '../lib/api';

/**
 * Shared FAAB-bid treatment for waiver recommendations: a prominent bid
 * range with a quieter budget-context caption underneath, instead of one
 * small line of footer metadata. Mirrors modules/faab.py's
 * `FaabGuidance.as_label()` formatting exactly (dollars when the league's
 * remaining budget is known, a percent-of-pool range otherwise) so this
 * never diverges from — or overstates the certainty of — the server's own
 * rule-of-thumb heuristic. Amber for the headline number: FAAB guidance is
 * acquisition/opportunity emphasis, the one fixed case this app's palette
 * reserves amber for.
 */
export default function FAABGuidance({
  faab,
  size = 'compact',
}: {
  faab: WaiverFaabGuidance;
  /** 'prominent' for the top waiver target, 'compact' for denser secondary
   * rows — both keep text at a comfortable mobile size, just fewer pixels
   * of padding/font-size between them. */
  size?: 'prominent' | 'compact';
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const hasDollars = faab.dollars_known && faab.remaining != null;
  const primary = hasDollars ? `$${faab.low_bid}–$${faab.high_bid}` : `${faab.pct_low}–${faab.pct_high}%`;
  const secondary = hasDollars ? `of $${faab.remaining} remaining` : 'of remaining FAAB';
  const prominent = size === 'prominent';
  return (
    <View style={styles.wrap}>
      <View style={styles.primaryRow}>
        <Ionicons name="cash-outline" size={prominent ? 15 : 12} color={colors.premium} />
        <AppText style={[styles.primary, prominent && styles.primaryProminent]} numberOfLines={1}>
          {primary}
        </AppText>
      </View>
      <AppText style={[styles.secondary, prominent && styles.secondaryProminent]} numberOfLines={1}>
        {secondary}
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { alignItems: 'flex-start', gap: 1 },
    primaryRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    primary: { fontSize: 14, fontWeight: '800', color: colors.premium },
    primaryProminent: { fontSize: 19, fontWeight: '800' },
    secondary: { fontSize: 10, color: colors.textTertiary },
    secondaryProminent: { fontSize: 11.5 },
  });
}
