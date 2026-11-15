import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { WaiverFaabGuidance } from '../lib/api';
import { faabDisplayText } from '../lib/faabDisplay';
import Money from './Money';

/**
 * Shared FAAB-bid treatment for waiver recommendations: a prominent bid
 * range with a quieter budget-context caption underneath, instead of one
 * small line of footer metadata. Mirrors modules/faab.py's
 * `FaabGuidance.as_label()` formatting exactly (dollars when the league's
 * remaining budget is known, a percent-of-pool range otherwise) so this
 * never diverges from — or overstates the certainty of — the server's own
 * rule-of-thumb heuristic. Green for the headline number: coridian_ called
 * out FAAB stats/value reading as amber/yellow (screenshot, 2026-09-23); all
 * money is now the one `money` green via <Money>.
 */
export default function FAABGuidance({
  faab,
  size = 'compact',
}: {
  /** Null / `applicable: false` in leagues without FAAB (Sleeper rolling or
   * reverse-standings waivers): renders a claim label, never dollars. */
  faab: WaiverFaabGuidance | null | undefined;
  /** 'prominent' for the top waiver target, 'compact' for denser secondary
   * rows — both keep text at a comfortable mobile size, just fewer pixels
   * of padding/font-size between them. */
  size?: 'prominent' | 'compact';
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const prominent = size === 'prominent';
  const { isBid, primary, secondary } = faabDisplayText(faab);
  return (
    <View style={styles.wrap}>
      <View style={styles.primaryRow}>
        <Ionicons
          name={isBid ? 'cash-outline' : 'swap-vertical-outline'}
          size={prominent ? 15 : 12}
          color={isBid ? colors.money : colors.textSecondary}
        />
        <Money
          all={isBid}
          style={[isBid ? styles.primary : styles.claim, prominent && styles.primaryProminent]}
          numberOfLines={1}
        >
          {primary}
        </Money>
      </View>
      <Money style={[styles.secondary, prominent && styles.secondaryProminent]} numberOfLines={1}>
        {secondary}
      </Money>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { alignItems: 'flex-start', gap: 1 },
    primaryRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    primary: { fontSize: 15.5, fontWeight: '800' },
    primaryProminent: { fontSize: 20.5, fontWeight: '800' },
    claim: { fontSize: 15.5, fontWeight: '800', color: colors.textSecondary },
    secondary: { fontSize: 12, color: colors.textTertiary },
    secondaryProminent: { fontSize: 13 },
  });
}
