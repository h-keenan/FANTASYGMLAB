import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import { api, type RecapStory, type WeeklyRecap } from '../lib/api';
import { colors, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Recap'>;

export default function RecapScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [recap, setRecap] = useState<WeeklyRecap | null>(null);
  const [notReady, setNotReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: `Recap — ${leagueName}` });
  }, [leagueName, navigation]);

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
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.headline}>{recap.headline}</Text>
      {recap.incomplete ? (
        <Text style={styles.incompleteNotice}>{recap.empty_reason || 'Not enough historical data yet.'}</Text>
      ) : (
        recap.stories.map((story, index) => <StoryCard key={`${story.story_type}-${index}`} story={story} />)
      )}
    </ScrollView>
  );
}

function StoryCard({ story }: { story: RecapStory }) {
  return (
    <AnimatedCard style={styles.storyCard}>
      <Text style={styles.storyTitle}>{story.title}</Text>
      <Text style={styles.storySummary}>{story.summary}</Text>
      {story.metric_label ? (
        <View style={styles.metricRow}>
          <Text style={styles.metricLabel}>{story.metric_label}</Text>
          <Text style={styles.metricValue}>{story.metric_value}</Text>
        </View>
      ) : null}
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  headline: { fontSize: 22, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.lg },
  incompleteNotice: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: spacing.xl },
  storyCard: { padding: spacing.lg, marginBottom: spacing.sm },
  storyTitle: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.xs },
  storySummary: { fontSize: 14, color: colors.textPrimary, lineHeight: 20 },
  metricRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  metricLabel: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },
  metricValue: { fontSize: 12, color: colors.textPrimary, fontWeight: '700' },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
});
