import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import AnimatedCard from './AnimatedCard';
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
  const styles = useMemo(() => createStyles(colors), [colors]);
  const note = holdIdeasNote(hold, ideaCount);
  return (
    <AnimatedCard style={styles.card}>
      <AppText style={styles.title}>{hold.headline}</AppText>
      {hold.why.map((line, index) => (
        <AppText key={`${line.factor}-${index}`} style={styles.line}>
          <AppText style={styles.factor}>{holdFactorLabel(line.factor)}: </AppText>
          {line.text}
        </AppText>
      ))}
      <BeginnerHelp term="tradeHubHold" />
      {note ? <AppText style={styles.note}>{note}</AppText> : null}
    </AnimatedCard>
  );
}

const createStyles = (colors: ThemeColors) =>
  StyleSheet.create({
    card: { padding: spacing.md, marginTop: spacing.sm, marginBottom: spacing.md, gap: 4 },
    title: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    line: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
    factor: { fontSize: 13, fontWeight: '600', color: colors.textTertiary },
    note: { fontSize: 12, fontWeight: '600', color: colors.textTertiary, marginTop: 2 },
  });
