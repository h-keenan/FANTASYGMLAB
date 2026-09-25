import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import TeamAvatar from '../components/TeamAvatar';
import { api, type MatchupComparison, type MatchupResponse, type MatchupSide, type MatchupStarter } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
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

function edgeColor(colors: ThemeColors): Record<MatchupComparison['edge'], string> {
  return {
    you: colors.successBright,
    opponent: colors.danger,
    even: colors.textSecondary,
  };
}

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

/**
 * `why` is server-composed as `" · "`-joined clauses in a fixed order —
 * tier, opportunity label, season-value rank-on-roster, injury note (see
 * `_matchup_starter_why` in services/mobile_api_service.py) — so the tier
 * and opportunity clauses can be stripped safely by position rather than by
 * fuzzy text matching. What's left (usually just the rank clause) becomes
 * the row's one-line supporting context; the tier/opportunity themselves
 * already render as the row's compact label, and injury already renders as
 * its own pill, so neither needs to repeat here.
 */
function deriveContextLine(player: MatchupStarter): string | null {
  const why = (player.why ?? '').trim();
  if (!why) return null;
  let parts = why.split(' · ').map((part) => part.trim()).filter(Boolean);
  if (parts.length && /\btier$/i.test(parts[0])) {
    parts = parts.slice(1);
  }
  const opportunity = (player.opportunity_label ?? '').trim().toLowerCase();
  if (parts.length && opportunity && parts[0].toLowerCase() === opportunity) {
    parts = parts.slice(1);
  }
  // Injury clauses are always the last bit and always contain this em-dash
  // separator — drop them here since the injury pill already covers it.
  parts = parts.filter((part) => !part.includes(' — '));
  if (parts.length === 0) return null;
  const phrase = parts.join(' · ');
  return phrase.charAt(0).toUpperCase() + phrase.slice(1);
}

export default function MatchupScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Matchup', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

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
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  if (!matchup || !matchup.my_team || !matchup.opponent || !matchup.comparison) {
    const reason = matchup?.reason ?? '';
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notice}>
          {NOT_READY_MESSAGES[reason] ?? "Couldn't build this week's matchup for this league."}
        </AppText>
      </View>
    );
  }

  const { my_team: mine, opponent, comparison, week } = matchup;
  const openPlayer = (player: MatchupStarter) =>
    navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName });

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <AnimatedCard glow style={styles.headlineCard}>
          <View style={styles.weekRow}>
            <Ionicons name="american-football-outline" size={14} color={colors.accent} />
            <AppText style={styles.weekLabel}>{week != null ? `WEEK ${week}` : 'THIS WEEK'}</AppText>
          </View>

          <View style={styles.versusRow}>
            <View style={styles.versusSide}>
              <TeamAvatar
                avatarId={mine.avatar_url}
                size={52}
                style={StyleSheet.flatten([styles.versusAvatar, { borderColor: colors.accent }])}
              />
              <AppText style={styles.versusTeam} numberOfLines={2}>
                {mine.team_name}
              </AppText>
              <AppText style={styles.versusRecord}>{recordLabel(mine)}</AppText>
              <AppText style={[styles.versusValue, { color: edgeColor(colors)[comparison.edge === 'you' ? 'you' : 'even'] }]}>
                {Math.round(comparison.my_season_value).toLocaleString()}
              </AppText>
            </View>
            <AppText style={styles.versusDivider}>VS</AppText>
            <View style={styles.versusSide}>
              <TeamAvatar
                avatarId={opponent.avatar_url}
                size={52}
                style={StyleSheet.flatten([styles.versusAvatar, { borderColor: colors.violet }])}
              />
              <AppText style={styles.versusTeam} numberOfLines={2}>
                {opponent.team_name}
              </AppText>
              <AppText style={styles.versusRecord}>{recordLabel(opponent)}</AppText>
              <AppText
                style={[styles.versusValue, { color: edgeColor(colors)[comparison.edge === 'opponent' ? 'you' : 'even'] }]}
              >
                {Math.round(comparison.opponent_season_value).toLocaleString()}
              </AppText>
            </View>
          </View>

          <ValueSplitBar comparison={comparison} />

          <View style={styles.verdictBlock}>
            <AppText style={[styles.edgeHeadline, { color: edgeColor(colors)[comparison.edge] }]}>
              {comparison.headline}
              {comparison.edge === 'even' ? '' : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
            </AppText>
            {/* Rendered straight from the API so this line can never drift
                into claiming more than the data behind it. */}
            <AppText style={styles.basisLabel}>{comparison.basis_label}</AppText>
          </View>
        </AnimatedCard>

        <ScreenInfoNote
          text="Starters on both sides are each roster's best available lineup by season-long value — the same optimal-lineup logic My Team uses, run for your opponent too so the comparison is apples to apples. It isn't necessarily the lineup they've set in Sleeper, and it doesn't account for this week's opponent defenses or weather."
        />

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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <View style={[styles.sectionAccentBar, { backgroundColor: accent }]} />
        <AppText style={styles.sectionLabel} numberOfLines={1}>
          {title.toUpperCase()}
        </AppText>
        <AppText style={[styles.sectionTotal, { color: accent }]} numberOfLines={1}>
          {Math.round(side.season_value_total).toLocaleString()} SEASON VALUE
        </AppText>
      </View>
      <AnimatedCard style={styles.sectionCard}>
        {side.starters.length === 0 ? (
          <AppText style={styles.emptySection}>No startable players on this roster right now.</AppText>
        ) : (
          side.starters.map((player, index) => (
            <PlayerIdentityRow
              key={`${side.roster_id}-${player.player_id}`}
              playerId={player.player_id}
              name={player.name}
              position={player.position}
              team={player.team}
              tier={player.tier}
              slot={player.slot ?? player.position}
              opportunityLabel={player.opportunity_label}
              contextLine={deriveContextLine(player)}
              injuryLabel={player.injury_label}
              ruledOut={player.ruled_out}
              onPress={() => onPressPlayer(player)}
              showDivider={index < side.starters.length - 1}
            />
          ))
        )}
      </AnimatedCard>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
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
  versusAvatar: { borderWidth: 2, marginBottom: spacing.xs },
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
    height: 8,
    borderRadius: radii.pill,
    overflow: 'hidden',
    marginTop: spacing.md,
    backgroundColor: colors.backgroundElevated,
  },
  splitFill: { height: '100%' },
  verdictBlock: { marginTop: spacing.md },
  edgeHeadline: { fontSize: 14, fontWeight: '700' },
  basisLabel: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs },
  section: { marginTop: spacing.md },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  sectionAccentBar: { width: 3, height: 14, borderRadius: radii.pill },
  sectionLabel: {
    flex: 1,
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionTotal: { fontSize: 13, fontWeight: '800', letterSpacing: 0.3 },
  sectionCard: { padding: spacing.md, paddingVertical: spacing.xs },
  emptySection: { fontSize: 13, color: colors.textSecondary, paddingVertical: spacing.sm },
  notice: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
