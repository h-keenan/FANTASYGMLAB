import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { api } from '../lib/api';
import { setLastLeague } from '../lib/lastLeague';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface LeagueSummary {
  season: string;
  week: string;
  teamCount: string;
  scoring: string;
}

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const QUICK_ACTIONS: Array<{ label: string; route: string; icon: IconName }> = [
  { label: 'Next Move', route: 'Dashboard', icon: 'flash-outline' },
  { label: 'Teams', route: 'Teams', icon: 'people-circle-outline' },
  { label: 'Players', route: 'Players', icon: 'people-outline' },
  { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline' },
  { label: 'Trade Hub', route: 'TradeHub', icon: 'shuffle-outline' },
  { label: 'Trade\nAnalyzer', route: 'TradeAnalyzer', icon: 'git-compare-outline' },
  { label: 'GM Targets', route: 'GmTargets', icon: 'bookmark-outline' },
  { label: 'Recap', route: 'Recap', icon: 'newspaper-outline' },
  { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline' },
];

function scoringLabel(scoringSettings: Record<string, unknown> | undefined): string {
  const rec = Number(scoringSettings?.rec ?? 0);
  if (rec >= 1) return 'PPR';
  if (rec > 0) return 'Half PPR';
  return 'Standard';
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [summary, setSummary] = useState<LeagueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: leagueName });
  }, [leagueName, navigation]);

  useEffect(() => {
    void setLastLeague({ leagueId, leagueName });
  }, [leagueId, leagueName]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const leagueResult = await api.getLeague(leagueId).catch(() => null);
        if (cancelled) return;

        if (leagueResult?.league) {
          const league = leagueResult.league;
          const settings = (league.settings as Record<string, unknown>) ?? {};
          setSummary({
            season: String(league.season ?? '—'),
            week: settings.leg ? String(settings.leg) : '—',
            teamCount: String(league.total_rosters ?? '—'),
            scoring: scoringLabel(league.scoring_settings as Record<string, unknown>),
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load league.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
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

  return (
    <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
      {summary ? (
        <View style={styles.summaryRow}>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{summary.season}</Text>
            <Text style={styles.summaryLabel}>Season</Text>
          </View>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{summary.week}</Text>
            <Text style={styles.summaryLabel}>Week</Text>
          </View>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{summary.teamCount}</Text>
            <Text style={styles.summaryLabel}>Teams</Text>
          </View>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{summary.scoring}</Text>
            <Text style={styles.summaryLabel}>Scoring</Text>
          </View>
        </View>
      ) : null}

      <View style={styles.quickActionsGrid}>
        {QUICK_ACTIONS.map((action) => (
          <TouchableOpacity
            key={action.route}
            style={styles.quickActionTile}
            onPress={() =>
              (navigation.navigate as (name: string, params?: object) => void)(action.route, {
                leagueId,
                leagueName,
              })
            }
          >
            <Ionicons name={action.icon} size={22} color={colors.accent} />
            <Text style={styles.quickActionLabel}>{action.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  list: { backgroundColor: colors.background },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  summaryRow: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
  },
  summaryStat: { flex: 1, alignItems: 'center' },
  summaryValue: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  summaryLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  quickActionTile: {
    width: '31%',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    alignItems: 'center',
    gap: spacing.xs,
  },
  quickActionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  error: { color: colors.danger, textAlign: 'center' },
});
