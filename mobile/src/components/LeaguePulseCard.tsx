import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import TeamAvatar from './TeamAvatar';
import { useThemeMode } from '../context/ThemeModeContext';
import { leaguePulseHighlights, type PulseTeam, type PulseTone } from '../lib/leaguePulse';
import { spacing, type ThemeColors } from '../theme';

/**
 * Shared "League Activity" tile (mirrors web-next's LeaguePulseCard, same
 * data and tile set: Most Active Manager, Hot Streak, Cold Streak from the
 * league's team-rankings). Renders nothing when no team stands out, like
 * web. Card chrome comes from AnimatedCard (glass tokens, lib/glass.ts).
 */
export default function LeaguePulseCard({
  teams,
  onPress,
}: {
  teams: PulseTeam[];
  onPress?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const highlights = leaguePulseHighlights(teams);
  if (highlights.length === 0) return null;
  const toneColor = (tone: PulseTone) =>
    tone === 'positive' ? colors.success : tone === 'negative' ? colors.danger : colors.textSecondary;

  return (
    <AnimatedCard style={styles.card} onPress={onPress} accessibilityLabel="League activity, open league recap">
      <View style={styles.header}>
        <AppText style={styles.title}>League Activity</AppText>
        <Ionicons name="chevron-forward" size={16} color={colors.accent} />
      </View>
      {highlights.map((h) => (
        <View key={h.key} style={styles.row}>
          <TeamAvatar avatarId={h.team.avatar_url} name={h.team.team_name} size={28} />
          <View style={styles.text}>
            <AppText style={[styles.label, { color: toneColor(h.tone) }]}>{h.label.toUpperCase()}</AppText>
            <AppText style={styles.team} numberOfLines={1}>
              {h.team.team_name || 'Team'}
            </AppText>
          </View>
          <AppText style={[styles.metric, { color: toneColor(h.tone) }]}>{h.metric}</AppText>
        </View>
      ))}
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { flex: 1, padding: spacing.md, gap: spacing.sm },
    header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    title: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, flexShrink: 1 },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    text: { flex: 1, minWidth: 0 },
    label: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
    team: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    metric: { fontSize: 14, fontWeight: '800', flexShrink: 0 },
  });
}
