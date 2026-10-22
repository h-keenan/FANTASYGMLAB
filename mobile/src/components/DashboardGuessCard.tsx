import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type GuessThePlayerResponse } from '../lib/api';
import { guessThePlayerStreakCaption } from '../lib/guessThePlayerPrompt';
import { requestGuessThePlayer } from '../lib/orbEvents';
import { spacing, type ThemeColors } from '../theme';

/**
 * Dashboard teaser for today's Guess the Player (sits beside League
 * Activity). It shows the real hidden-player prompt (position, week, first
 * stats) and the real streak; tapping re-opens the existing daily prompt,
 * which owns answering. Renders nothing when there is no prompt or it was
 * already answered (the prompt's own reveal covers that). Silent on fetch
 * failure: a bonus extra, never blocks the screen.
 */
export default function DashboardGuessCard() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [response, setResponse] = useState<GuessThePlayerResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGuessThePlayer()
      .then((result) => {
        if (!cancelled) setResponse(result);
      })
      .catch(() => {
        if (!cancelled) setResponse(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const prompt = response?.prompt;
  if (!response || !prompt || response.already_answered) return null;
  const stats = prompt.stat_line
    .slice(0, 3)
    .map((item) => `${item.value} ${item.label}`)
    .join(' · ');

  return (
    <AnimatedCard style={styles.card} onPress={requestGuessThePlayer}>
      <View style={styles.headerRow}>
        <AppText style={styles.title}>Guess the Player</AppText>
        <Ionicons name="chevron-forward" size={16} color={colors.accent} />
      </View>
      <View style={styles.identityRow}>
        <View style={styles.avatar} />
        <View style={styles.identityText}>
          <AppText style={styles.hidden}>??? ???</AppText>
          <View style={styles.metaRow}>
            <PositionBadge position={prompt.position} />
            <AppText style={styles.meta}>
              Wk {prompt.week} · {prompt.season}
            </AppText>
          </View>
        </View>
      </View>
      <AppText style={styles.stats} numberOfLines={2}>
        {stats}
      </AppText>
      <AppText style={styles.streak}>{guessThePlayerStreakCaption(response.streak)}</AppText>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { flex: 1, padding: spacing.md, gap: spacing.sm },
    headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    title: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, flexShrink: 1 },
    identityRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.backgroundElevated, borderWidth: 1, borderColor: colors.border },
    identityText: { flex: 1, gap: 2 },
    hidden: { fontSize: 14, fontWeight: '700', color: colors.textTertiary },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    meta: { fontSize: 11, color: colors.textSecondary },
    stats: { fontSize: 12, color: colors.textSecondary },
    streak: { fontSize: 11, color: colors.textTertiary },
  });
}
