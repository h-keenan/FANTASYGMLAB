import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import InfoMark from './InfoMark';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import AccentCard from './AccentCard';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TradeHubHold } from '../lib/api';
import { holdFactorLabel, holdIdeasNote } from '../lib/tradeHubHold';
import { spacing, type ThemeColors } from '../theme';

/**
 * The explicit "hold" answer (no trade) with a short multi-factor why. Every
 * line is built server-side from real engine inputs; this only renders it.
 * Mirrors web-next's TradeHubHoldCard.
 */
export default function TradeHubHoldCard({ hold, ideaCount }: { hold: TradeHubHold; ideaCount: number }) {
  const { colors } = useThemeMode();
  const copy = useExperienceCopy();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const note = holdIdeasNote(hold, ideaCount);
  const factorStyle = (factor: string): { color: string; icon: keyof typeof Ionicons.glyphMap } => {
    if (factor === 'context') return { color: colors.accent, icon: 'pulse-outline' };
    if (factor === 'ideas') return { color: colors.success, icon: 'bulb-outline' };
    if (factor === 'competition') return { color: colors.warning, icon: 'people-outline' };
    if (factor === 'posture') return { color: colors.accent, icon: 'shield-outline' };
    return { color: colors.textTertiary, icon: 'ellipse-outline' };
  };
  return (
    <AccentCard accent={colors.accent} style={styles.card}>
      <View style={styles.head}>
        <View style={[styles.glyph, { backgroundColor: colors.accentMuted }]}>
          <Ionicons name="pause-outline" size={18} color={colors.accent} />
        </View>
        <View style={styles.headText}>
          <ToneBadge label="Hold" color={colors.accent} />
          <View style={styles.titleRow}>
            <AppText style={[styles.title, styles.titleText]}>{hold.headline}</AppText>
            <InfoMark label="this hold" beginnerOnly lines={[copy.help('tradeHubHold')]} />
          </View>
        </View>
      </View>
      {hold.why.map((line, index) => {
        const fs = factorStyle(line.factor);
        return (
          <View key={`${line.factor}-${index}`} style={styles.row}>
            <View style={[styles.glyph, { backgroundColor: fs.color + '26' }]}>
              <Ionicons name={fs.icon} size={16} color={fs.color} />
            </View>
            <View style={styles.rowText}>
              <ToneBadge label={holdFactorLabel(line.factor)} color={fs.color} />
              <AppText style={styles.line}>{line.text}</AppText>
            </View>
          </View>
        );
      })}
      {note ? <AppText style={styles.note}>{note}</AppText> : null}
    </AccentCard>
  );
}

const createStyles = (colors: ThemeColors) =>
  StyleSheet.create({
    card: { marginTop: spacing.sm, marginBottom: spacing.md },
    head: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    titleRow: { flexDirection: 'row', alignItems: 'center', alignSelf: 'stretch' },
    titleText: { flexShrink: 1 },
    headText: { flex: 1, alignItems: 'flex-start', gap: 4 },
    glyph: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
    row: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
    rowText: { flex: 1, alignItems: 'flex-start', gap: 4 },
    title: { fontSize: 16.5, fontWeight: '700', color: colors.textPrimary },
    line: { fontSize: 14.5, lineHeight: 20, color: colors.textSecondary },
    note: { fontSize: 13.5, fontWeight: '600', color: colors.textTertiary, marginTop: 2 },
  });
