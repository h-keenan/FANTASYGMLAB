import React, { useCallback, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import TierBadge from '../components/TierBadge';
import { api, type MatchupComparison, type MatchupResponse, type MatchupSide, type MatchupStarter } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Matchup'>;

/**
 * This week's head-to-head, ranked by SEASON-LONG value/opportunity signal.
 *
 * Not a points projection, and the copy on this screen must never imply one:
 * the app has no weekly-projection feed and no opponent-defense-strength
 * data, so every "why" here is season form (tier, workload/opportunity
 * label, season-value rank on that roster, injury tag). The API says the
 * same thing in `basis_label`, which this screen renders verbatim rather
 * than paraphrasing into something stronger than the data supports.
 */

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    'Link your Sleeper username on the web app first — the matchup view needs to know which roster is yours.',
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
  no_player_data: "Player data isn't available right now — try again in a bit.",
  no_current_week: "This league hasn't started a week yet.",
  no_matchup_data: "Sleeper doesn't have matchups posted for this week yet.",
  roster_not_in_matchups: "Your roster isn't in this week's matchup list.",
  bye_week: "You're not paired against anyone this week — enjoy the bye.",
  opponent_roster_missing: "Couldn't load your opponent's roster right now — try again in a bit.",
};

const EDGE_COLOR: Record<MatchupComparison['edge'], string> = {
  you: colors.successBright,
  opponent: colors.danger,
  even: colors.textSecondary,
};

function recordLabel(side: MatchupSide): string {
  if (side.wins == null || side.losses == null) return '—';
  return `${side.wins}-${side.losses}${side.ties ? `-${side.ties}` : ''}`;
}

function toRankedPlayer(player: MatchupStarter) {
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

export default function MatchupScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Matchup', leagueName);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const result = await api.getLeagueMatchup(leagueId);
          if (!cancelled) setMatchup(result);
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load this week’s matchup.');
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
    return <BrandedSpinner style={styles.center} />;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (!matchup || !matchup.my_team || !matchup.opponent || !matchup.comparison) {
    const reason = matchup?.reason ?? '';
    return (
      <View style={styles.center}>
        <Text style={styles.notice}>
          {NOT_READY_MESSAGES[reason] ?? "Couldn't build this week's matchup for this league."}
        </Text>
      </View>
    );
  }

  const { my_team: mine, opponent, comparison, week } = matchup;
  const openPlayer = (player: MatchupStarter) =>
    navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName });

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <AnimatedCard glow style={styles.headlineCard}>
          <View style={styles.weekRow}>
            <Ionicons name="american-football-outline" size={14} color={colors.accent} />
            <Text style={styles.weekLabel}>{week != null ? `WEEK ${week}` : 'THIS WEEK'}</Text>
          </View>

          <View style={styles.versusRow}>
            <View style={styles.versusSide}>
              <Text style={styles.versusTeam} numberOfLines={2}>
                {mine.team_name}
              </Text>
              <Text style={styles.versusRecord}>{recordLabel(mine)}</Text>
              <Text style={[styles.versusValue, { color: EDGE_COLOR[comparison.edge === 'you' ? 'you' : 'even'] }]}>
                {Math.round(comparison.my_season_value).toLocaleString()}
              </Text>
            </View>
            <Text style={styles.versusDivider}>VS</Text>
            <View style={styles.versusSide}>
              <Text style={styles.versusTeam} numberOfLines={2}>
                {opponent.team_name}
              </Text>
              <Text style={styles.versusRecord}>{recordLabel(opponent)}</Text>
              <Text
                style={[styles.versusValue, { color: EDGE_COLOR[comparison.edge === 'opponent' ? 'you' : 'even'] }]}
              >
                {Math.round(comparison.opponent_season_value).toLocaleString()}
              </Text>
            </View>
          </View>

          <ValueSplitBar comparison={comparison} />

          <Text style={[styles.edgeHeadline, { color: EDGE_COLOR[comparison.edge] }]}>
            {comparison.headline}
            {comparison.edge === 'even' ? '' : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
          </Text>
          {/* Rendered straight from the API so this line can never drift
              into claiming more than the data behind it. */}
          <Text style={styles.basisLabel}>{comparison.basis_label}</Text>
        </AnimatedCard>

        <Text style={styles.disclaimer}>
          Starters on both sides are each roster's best available lineup by season-long value — the same
          optimal-lineup logic My Team uses, run for your opponent too so the comparison is apples to apples. It
          isn't necessarily the lineup they've set in Sleeper, and it doesn't account for this week's opponent
          defenses or weather.
        </Text>

        <StarterSection title="Your suggested starters" side={mine} onPressPlayer={openPlayer} accent={colors.accent} />
        <StarterSection
          title={`${opponent.team_name}'s best lineup`}
          side={opponent}
          onPressPlayer={openPlayer}
          accent={colors.violet}
        />
      </ScrollView>
    </View>
  );
}

function ValueSplitBar({ comparison }: { comparison: MatchupComparison }) {
  const total = comparison.my_season_value + comparison.opponent_season_value;
  const mineShare = total > 0 ? Math.max(0.05, Math.min(0.95, comparison.my_season_value / total)) : 0.5;
  return (
    <View style={styles.splitBar}>
      <View style={[styles.splitFill, { flex: mineShare, backgroundColor: colors.accent }]} />
      <View style={[styles.splitFill, { flex: 1 - mineShare, backgroundColor: colors.violet }]} />
    </View>
  );
}

function StarterSection({
  title,
  side,
  onPressPlayer,
  accent,
}: {
  title: string;
  side: MatchupSide;
  onPressPlayer: (player: MatchupStarter) => void;
  accent: string;
}) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <Text style={styles.sectionLabel} numberOfLines={1}>
          {title.toUpperCase()}
        </Text>
        <Text style={[styles.sectionTotal, { color: accent }]}>
          {Math.round(side.season_value_total).toLocaleString()} SEASON VALUE
        </Text>
      </View>
      {side.starters.length === 0 ? (
        <Text style={styles.emptySection}>No startable players on this roster right now.</Text>
      ) : (
        side.starters.map((player) => (
          <StarterRow key={`${side.roster_id}-${player.player_id}`} player={player} onPress={() => onPressPlayer(player)} />
        ))
      )}
    </View>
  );
}

function StarterRow({ player, onPress }: { player: MatchupStarter; onPress: () => void }) {
  return (
    <AnimatedCard style={styles.card} onPress={onPress}>
      <View style={styles.cardTopRow}>
        <View style={styles.slotBadge}>
          <Text style={styles.slotText}>{player.slot ?? player.position ?? '—'}</Text>
        </View>
        <PlayerAvatar playerId={player.player_id} size={40} tier={player.tier} style={styles.avatar} />
        <View style={styles.nameColumn}>
          <Text style={styles.name} numberOfLines={1}>
            {player.name ?? 'Unknown player'}
          </Text>
          <View style={styles.metaRow}>
            <PositionBadge position={player.position} />
            <TierBadge storedTier={player.tier} />
            <Text style={styles.meta} numberOfLines={1}>
              {player.team ?? '—'}
            </Text>
          </View>
        </View>
        {player.injury_label ? (
          <View style={[styles.injuryPill, player.ruled_out && styles.injuryPillOut]}>
            <Text style={[styles.injuryText, player.ruled_out && styles.injuryTextOut]}>
              {player.injury_label}
            </Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.why} numberOfLines={3}>
        {player.why}
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
  headlineCard: { padding: spacing.lg, marginBottom: spacing.md },
  weekRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.md },
  weekLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 0.8, color: colors.accent },
  versusRow: { flexDirection: 'row', alignItems: 'flex-start' },
  versusSide: { flex: 1 },
  versusTeam: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  versusRecord: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
  versusValue: { fontSize: 22, fontWeight: '800', marginTop: spacing.xs },
  versusDivider: {
    fontSize: 11,
    fontWeight: '800',
    color: colors.textTertiary,
    letterSpacing: 0.8,
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.xs,
  },
  splitBar: {
    flexDirection: 'row',
    height: 6,
    borderRadius: radii.pill,
    overflow: 'hidden',
    marginTop: spacing.md,
    backgroundColor: colors.backgroundElevated,
  },
  splitFill: { height: '100%' },
  edgeHeadline: { fontSize: 14, fontWeight: '700', marginTop: spacing.md },
  basisLabel: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs },
  disclaimer: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginBottom: spacing.md },
  section: { marginTop: spacing.md },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  sectionLabel: {
    flex: 1,
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionTotal: { fontSize: 10, fontWeight: '800', letterSpacing: 0.4 },
  emptySection: { fontSize: 13, color: colors.textSecondary },
  card: { padding: spacing.md, marginBottom: spacing.sm },
  cardTopRow: { flexDirection: 'row', alignItems: 'center' },
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
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2, flexWrap: 'wrap' },
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  injuryPill: {
    backgroundColor: colors.dangerMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  injuryText: { fontSize: 11, fontWeight: '700', color: colors.danger },
  // A ruled-out starter is only here because nothing available could fill
  // the slot — a solid pill so it can't read as an ordinary injury note.
  injuryPillOut: { backgroundColor: colors.danger },
  injuryTextOut: { color: colors.badgeText },
  why: { fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginTop: spacing.sm },
  notice: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
});
