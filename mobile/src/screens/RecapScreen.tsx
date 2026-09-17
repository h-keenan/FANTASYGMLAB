import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import RecapSharePreviewModal from '../components/RecapSharePreviewModal';
import { api, type RecapStory, type WeeklyRecap } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Recap'>;

const STORY_META: Record<
  string,
  { icon: React.ComponentProps<typeof Ionicons>['name']; color: string }
> = {
  performance: { icon: 'trophy', color: colors.premium },
  matchup: { icon: 'flame', color: colors.danger },
  waiver: { icon: 'cash-outline', color: colors.success },
  trade: { icon: 'swap-horizontal', color: colors.accent },
  activity: { icon: 'repeat', color: colors.violet },
  roster_riser: { icon: 'trending-up', color: colors.accent },
};
const DEFAULT_STORY_META = { icon: 'newspaper-outline' as const, color: colors.textSecondary };

export default function RecapScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [recap, setRecap] = useState<WeeklyRecap | null>(null);
  const [notReady, setNotReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);

  useScreenHeaderTitle(navigation, 'Recap', leagueName);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await api.getLeagueRecap(leagueId);
        if (cancelled) return;
        if (result.recap) {
          setRecap(result.recap);
        } else {
          setNotReady(true);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load recap.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (notReady || !recap) {
    return (
      <View style={styles.center}>
        <Text style={styles.notReadyText}>
          No recap is ready yet — check back after this week's matchups finish scoring.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <View style={styles.headerRow}>
        <View style={styles.headerTextGroup}>
          <Text style={styles.kicker}>LEAGUE MEMORY</Text>
          <Text style={styles.headline}>{recap.headline}</Text>
        </View>
        {!recap.incomplete ? (
          <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
            <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
            <Text style={styles.shareButtonText}>Share</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      {recap.incomplete ? (
        <Text style={styles.incompleteNotice}>{recap.empty_reason || 'Not enough historical data yet.'}</Text>
      ) : (
        recap.stories.map((story, index) => <StoryCard key={`${story.story_type}-${index}`} story={story} />)
      )}
      <RecapSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueName={leagueName}
        recap={recap}
      />
      </ScrollView>
    </View>
  );
}

function StoryCard({ story }: { story: RecapStory }) {
  const meta = STORY_META[story.story_type] ?? DEFAULT_STORY_META;
  const isMatchup = story.story_type === 'matchup';
  const isTrade = story.story_type === 'trade';

  return (
    <AnimatedCard style={styles.storyCard}>
      <View style={styles.storyHeaderRow}>
        <View style={[styles.iconDisc, { backgroundColor: `${meta.color}26` }]}>
          <Ionicons name={meta.icon} size={20} color={meta.color} />
        </View>
        <View style={styles.storyTextGroup}>
          <Text style={[styles.storyKicker, { color: meta.color }]}>
            {story.story_type.replace(/_/g, ' ').toUpperCase()}
          </Text>
          <Text style={styles.storyTitle} numberOfLines={1}>
            {story.title}
          </Text>
        </View>
        {story.metric_label ? (
          <View style={styles.metricGroup}>
            <Text style={[styles.metricValue, { color: meta.color }]}>{story.metric_value}</Text>
            <Text style={styles.metricLabel}>{story.metric_label.toUpperCase()}</Text>
          </View>
        ) : null}
      </View>

      {isMatchup ? (
        <View style={styles.matchupRow}>
          <Text style={styles.matchupTeam} numberOfLines={1}>
            {story.primary_team}
          </Text>
          <Text style={styles.matchupVs}>vs</Text>
          <Text style={[styles.matchupTeam, styles.matchupTeamMuted]} numberOfLines={1}>
            {story.secondary_team}
          </Text>
        </View>
      ) : null}

      {isTrade && story.secondary_team ? (
        <View style={styles.tradeRow}>
          <View style={styles.tradeChip}>
            <Text style={styles.tradeChipText} numberOfLines={1}>
              {story.primary_team}
            </Text>
          </View>
          <Ionicons name="swap-horizontal" size={14} color={colors.textTertiary} />
          <View style={styles.tradeChip}>
            <Text style={styles.tradeChipText} numberOfLines={1}>
              {story.secondary_team}
            </Text>
          </View>
        </View>
      ) : null}

      <Text style={styles.storySummary} numberOfLines={3}>
        {story.summary}
      </Text>
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.lg,
  },
  headerTextGroup: { flex: 1 },
  kicker: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.8, marginBottom: 4 },
  headline: { fontSize: 26, fontWeight: '700', color: colors.textPrimary },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: 2,
  },
  shareButtonText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  incompleteNotice: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: spacing.xl },
  storyCard: { marginBottom: spacing.sm },
  storyHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  iconDisc: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  storyTextGroup: { flex: 1 },
  storyKicker: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5, marginBottom: 2 },
  storyTitle: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  metricGroup: { alignItems: 'flex-end' },
  metricValue: { fontSize: 20, fontWeight: '700' },
  metricLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  matchupRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  matchupTeam: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  matchupTeamMuted: { color: colors.textSecondary, fontWeight: '500' },
  matchupVs: { fontSize: 11, color: colors.textTertiary, fontWeight: '600' },
  tradeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  tradeChip: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  tradeChipText: { fontSize: 12, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
  storySummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
});
