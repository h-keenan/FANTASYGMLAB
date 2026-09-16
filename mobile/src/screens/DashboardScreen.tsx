import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View, type ViewStyle } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import { api, type DashboardItem, type DashboardItemCategory } from '../lib/api';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Dashboard'>;

const CATEGORY_META: Record<
  DashboardItemCategory,
  { label: string; icon: React.ComponentProps<typeof Ionicons>['name']; color: string }
> = {
  top_priority: { label: 'Your Next Move', icon: 'flash', color: colors.accent },
  watch: { label: 'Watch', icon: 'eye-outline', color: colors.danger },
  waiver_opportunity: { label: 'Waiver Opportunity', icon: 'swap-horizontal-outline', color: colors.premium },
  league_movement: { label: 'League Movement', icon: 'trending-up-outline', color: colors.textSecondary },
};

export default function DashboardScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<DashboardItem[] | null>(null);
  const [quiet, setQuiet] = useState(false);
  const [quietReason, setQuietReason] = useState('');
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Next Move', leagueName);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await api.getLeagueDashboard(leagueId);
        if (cancelled) return;
        if (result.reason) {
          setNotReadyReason(result.reason);
        } else {
          setItems(result.items);
          setQuiet(result.quiet);
          setQuietReason(result.quiet_reason ?? '');
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load your Next Move briefing.');
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

  if (notReadyReason) {
    return (
      <View style={styles.center}>
        <Text style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build your Next Move briefing for this league."}
        </Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.disclaimer}>
        The real Next Move briefing for {leagueName} — the same roster-pressure, injury, need, and
        waiver signals the web app's Dashboard uses.
      </Text>
      {quiet || !items || items.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="checkmark-done-outline" size={22} color={colors.success} />
          <Text style={styles.emptyText}>
            {quietReason || 'Nothing urgent right now — your roster looks steady.'}
          </Text>
        </View>
      ) : (
        items.map((item, index) => <BriefingCard key={`${item.category}-${index}`} item={item} />)
      )}
    </ScrollView>
  );
}

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — the Next Move briefing needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
};

function BriefingCard({ item }: { item: DashboardItem }) {
  const meta = CATEGORY_META[item.category] ?? CATEGORY_META.watch;
  return (
    <AnimatedCard style={StyleSheet.flatten([styles.card, { borderLeftColor: meta.color } as ViewStyle])}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name={meta.icon} size={15} color={meta.color} style={styles.cardIcon} />
        <Text style={[styles.cardLabel, { color: meta.color }]}>{meta.label}</Text>
      </View>
      <Text style={styles.cardHeadline}>{item.headline}</Text>
      {item.reason ? <Text style={styles.cardReason}>{item.reason}</Text> : null}
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
  disclaimer: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.lg, lineHeight: 16 },
  card: {
    borderLeftWidth: 4,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
  cardIcon: { marginRight: spacing.xs },
  cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  cardHeadline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  cardReason: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  emptyText: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
});
