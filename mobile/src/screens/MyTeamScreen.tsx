import React, { useCallback, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import { api, type LineupPlayer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'MyTeam'>;

const NO_LEAGUE_REASONS = new Set([
  'no_sleeper_username_linked',
  'sleeper_user_not_found',
  'not_a_member_of_league',
]);

function reasonMessage(reason: string): string | null {
  if (NO_LEAGUE_REASONS.has(reason)) {
    return "Link your Sleeper account and join this league from Home to see your lineup.";
  }
  if (reason === 'empty_roster') {
    return "Your roster in this league looks empty.";
  }
  if (reason === 'no_player_data') {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}

function toRankedPlayer(player: LineupPlayer) {
  return {
    player_id: player.player_id,
    name: player.name,
    position: player.position,
    team: player.team,
    age: player.age,
    status: player.status,
    injury_status: player.injury_status,
    tier: player.tier,
    score: player.score,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: player.opportunity_label,
  };
}

export default function MyTeamScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [starters, setStarters] = useState<LineupPlayer[]>([]);
  const [bench, setBench] = useState<LineupPlayer[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'My Team', leagueName);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const result = await api.getLeagueMyTeam(leagueId);
          if (cancelled) return;
          setStarters(result.starters);
          setBench(result.bench);
          setNotice(result.reason ? reasonMessage(result.reason) : null);
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load your lineup.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [leagueId]),
  );

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

  if (notice) {
    return (
      <View style={styles.center}>
        <Text style={styles.notice}>{notice}</Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <Text style={styles.disclaimer}>
          Your suggested starting lineup for {leagueName} — the same optimal-lineup logic the web
          app's Dashboard and My Team pages use.
        </Text>

        <Text style={styles.sectionLabel}>Starters</Text>
        {starters.map((player) => (
          <LineupRow
            key={player.player_id}
            player={player}
            onPress={() => navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName })}
          />
        ))}

        <Text style={styles.sectionLabel}>Bench</Text>
        {bench.length === 0 ? (
          <Text style={styles.emptyBench}>No bench players.</Text>
        ) : (
          bench.map((player) => (
            <LineupRow
              key={player.player_id}
              player={player}
              onPress={() => navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName })}
            />
          ))
        )}
      </ScrollView>
    </View>
  );
}

function LineupRow({ player, onPress }: { player: LineupPlayer; onPress: () => void }) {
  return (
    <AnimatedCard style={styles.card} onPress={onPress}>
      <View style={styles.slotBadge}>
        <Text style={styles.slotText}>{player.slot === 'BENCH' ? player.position ?? '—' : player.slot}</Text>
      </View>
      <PlayerAvatar playerId={player.player_id} size={40} tier={player.tier} style={styles.avatar} />
      <View style={styles.nameColumn}>
        <Text style={styles.name} numberOfLines={1}>
          {player.name ?? 'Unknown player'}
        </Text>
        <View style={styles.metaRow}>
          <PositionBadge position={player.position} />
          <Text style={styles.meta} numberOfLines={1}>
            {[player.team, player.opportunity_label].filter(Boolean).join(' · ') || '—'}
          </Text>
        </View>
      </View>
      {player.injury_status ? (
        <View style={styles.injuryPill}>
          <Text style={styles.injuryText}>{player.injury_status}</Text>
        </View>
      ) : null}
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
  disclaimer: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginBottom: spacing.md },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  emptyBench: { fontSize: 13, color: colors.textSecondary },
  card: { flexDirection: 'row', alignItems: 'center', padding: spacing.md, marginBottom: spacing.sm },
  slotBadge: {
    width: 40,
    height: 26,
    borderRadius: radii.sm,
    backgroundColor: colors.badgeBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  slotText: { color: colors.badgeText, fontSize: 10, fontWeight: '700' },
  avatar: { marginRight: spacing.sm },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  injuryPill: {
    backgroundColor: colors.dangerMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  injuryText: { fontSize: 11, fontWeight: '700', color: colors.danger },
  notice: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
});
