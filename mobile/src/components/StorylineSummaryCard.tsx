import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { WeeklyRecap } from '../lib/api';
import { spacing, type ThemeColors } from '../theme';

/**
 * Compact "what's happening in the league right now" summary for League
 * Overview — coridian_'s 2026-10 brief asked for "storylines" underneath
 * the matchup and injury concerns. No existing compact widget covered this
 * (RecapScreen's own story cards are a full-page presentation, not a
 * dashboard-sized summary), so this is a minimal new component built
 * entirely from the already-fetched weekly recap (api.getLeagueRecap) —
 * the same `headline`/`stories[].title`/`stories[].summary` fields
 * RecapScreen itself renders, just the top couple of stories instead of the
 * full list, with a tap-through to the full Recap screen for the rest.
 * Nothing new from the backend.
 */
export default function StorylineSummaryCard({
  recap,
  onPress,
}: {
  recap: WeeklyRecap;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const topStories = recap.stories.slice(0, 2);

  return (
    <AnimatedCard
      style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.textSecondary }])}
      onPress={onPress}
    >
      <View style={styles.headerRow}>
        <Ionicons name="newspaper-outline" size={15} color={colors.textSecondary} style={styles.icon} />
        <AppText style={[styles.label, { color: colors.textSecondary }]}>
          {`WEEK ${recap.week} STORYLINES`.toUpperCase()}
        </AppText>
      </View>
      <AppText style={styles.headline} numberOfLines={2}>
        {recap.headline}
      </AppText>
      {topStories.length > 0 ? (
        <View style={styles.storyList}>
          {topStories.map((story, index) => (
            <View key={`${story.story_type}-${index}`} style={styles.storyRow}>
              <AppText style={styles.storyTitle} numberOfLines={1}>
                {story.title}
              </AppText>
              <AppText style={styles.storySummary} numberOfLines={2}>
                {story.summary}
              </AppText>
            </View>
          ))}
        </View>
      ) : null}
      <View style={styles.footerRow}>
        <AppText style={styles.footerText}>FULL RECAP</AppText>
        <Ionicons name="chevron-forward" size={14} color={colors.accentSoft} />
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      borderLeftWidth: 4,
      padding: spacing.lg,
      marginBottom: spacing.sm,
    },
    headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
    icon: { marginRight: spacing.xs },
    label: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
    headline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
    storyList: { gap: spacing.sm },
    storyRow: {
      paddingTop: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.hairline,
    },
    storyTitle: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    storySummary: { fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginTop: 2 },
    footerRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 2,
      marginTop: spacing.md,
    },
    footerText: { fontSize: 12, fontWeight: '700', color: colors.accentSoft, letterSpacing: 0.4 },
  });
}
