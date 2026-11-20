import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import PressableScale from './PressableScale';
import TeamNameLink from './TeamNameLink';
import { useThemeMode } from '../context/ThemeModeContext';
import { leaguePulseHighlights, type PulseTeam, type PulseTone } from '../lib/leaguePulse';
import { spacing, type ThemeColors } from '../theme';
import { toneColor as sharedToneColor } from '../lib/verdictToneTheme';

/**
 * Shared "League Activity" tile (mirrors web-next's LeaguePulseCard, same
 * data and tile set: Most Active Manager, Hot Streak, Cold Streak from the
 * league's team-rankings). Renders nothing when no team stands out, like
 * web. Card chrome comes from AnimatedCard (glass tokens, lib/glass.ts).
 */
export default function LeaguePulseCard({
  teams,
  onPress,
  leagueId,
  leagueName,
}: {
  teams: PulseTeam[];
  /** Opens the league recap; only the header is this target, each team name is its own team-sheet target. */
  onPress?: () => void;
  leagueId?: string | null;
  leagueName?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const highlights = leaguePulseHighlights(teams);
  if (highlights.length === 0) return null;
  const toneColor = (tone: PulseTone) =>
    tone === 'positive' ? colors.success : tone === 'negative' ? sharedToneColor(colors, 'negative') : colors.textSecondary;

  return (
    <AnimatedCard style={styles.card}>
      <PressableScale
        onPress={onPress}
        disabled={!onPress}
        accessibilityRole="button"
        accessibilityLabel="League activity, open league recap"
        style={styles.header}
      >
        <AppText style={styles.title}>League Activity</AppText>
        <Ionicons name="chevron-forward" size={16} color={colors.accent} />
      </PressableScale>
      {highlights.map((h) => (
        <View key={h.key} style={styles.row}>
          <View style={styles.text}>
            <AppText style={[styles.label, { color: toneColor(h.tone) }]}>{h.label.toUpperCase()}</AppText>
            <TeamNameLink
              leagueId={leagueId}
              leagueName={leagueName}
              rosterId={h.team.roster_id}
              name={h.team.team_name || 'Team'}
              avatarId={h.team.avatar_url}
              showAvatar
              avatarSize={28}
              textStyle={styles.team}
            />
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
    header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 44 },
    title: { fontSize: 16.5, fontWeight: '800', color: colors.textPrimary, flexShrink: 1 },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    text: { flex: 1, minWidth: 0 },
    label: { fontSize: 12, fontWeight: '700', letterSpacing: 0.4 },
    team: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    metric: { fontSize: 15.5, fontWeight: '800', flexShrink: 0 },
  });
}
