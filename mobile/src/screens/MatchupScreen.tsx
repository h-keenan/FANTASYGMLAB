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
import InsightRow from '../components/InsightRow';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import TeamAvatar from '../components/TeamAvatar';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import {
  api,
  type MatchupComparison,
  type MatchupRealComparison,
  type MatchupRealStarter,
  type MatchupResponse,
  type MatchupSide,
  type MatchupStarter,
} from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Matchup'>;

/**
 * This week's head-to-head: two distinct, clearly-labeled views.
 *
 * 1. REAL current-week lineup/points (`real_starters` / `real_points` /
 *    `real_comparison`) — Sleeper's own actual data for what each manager
 *    has started this week and how many points they've actually scored so
 *    far. Genuine, not computed by this app. Only rendered once Sleeper has
 *    populated it (`has_live_data`); this screen never fabricates a live
 *    score before then.
 * 2. SUGGESTED season-value lineup (`starters` / `season_value_total` /
 *    `comparison`) — this app's own best-available-lineup recommendation,
 *    ranked by SEASON-LONG value/opportunity signal, unchanged from before.
 *    Not a points projection, and the copy here must never imply one: the
 *    app has no weekly-projection feed and no opponent-defense-strength
 *    data, so every "why" is season form (tier, workload/opportunity label,
 *    season-value rank on that roster, injury tag). The API says the same
 *    thing in `basis_label`, rendered verbatim rather than paraphrased into
 *    something stronger than the data supports.
 *
 * Whichever view answers "what matters right now" gets the hero treatment:
 * once Sleeper reports live data for both sides, the hero numbers/verdict
 * switch to the real comparison (with the season-value comparison folded in
 * underneath, still visible, not removed); before that, the season-value
 * comparison is the hero exactly as it always was.
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

/** Icon paired with the verdict headline — same trending-up/down language
 * used for value-change indicators elsewhere in the app, so "the edge" reads
 * at a glance instead of only through color. */
function edgeIcon(edge: MatchupComparison['edge']): React.ComponentProps<typeof Ionicons>['name'] {
  if (edge === 'you') return 'trending-up';
  if (edge === 'opponent') return 'trending-down';
  return 'remove';
}

/** Headline for the REAL (live points) comparison — mirrors `comparison.headline`'s
 * tone but is composed client-side since the API's `real_comparison` intentionally
 * carries no headline field of its own (there's no "why" to explain, just a score). */
function realHeadline(realComparison: MatchupRealComparison): string {
  if (realComparison.edge === 'you') return "You're ahead on live points";
  if (realComparison.edge === 'opponent') return 'Your opponent is ahead on live points';
  return "It's tied on live points right now";
}

type InjuryWatchItem = {
  key: string;
  player: MatchupStarter;
  sideLabel: string;
};

/**
 * Pulls every flagged starter (either side) into one flat list so risk is
 * visible near the top of the screen instead of only surfacing wherever that
 * player's row happens to fall in a long lineup scroll — the brief's "make
 * injury/risk states immediately obvious" requirement, applied at the page
 * level rather than only the row level. Purely a client-side presentation
 * grouping of data already on the response; no new business logic.
 */
function collectInjuryWatch(mine: MatchupSide, opponent: MatchupSide): InjuryWatchItem[] {
  const items: InjuryWatchItem[] = [];
  const pushFrom = (side: MatchupSide, sideLabel: string) => {
    side.starters.forEach((player) => {
      if (player.injury_label) {
        items.push({ key: `${side.roster_id}-${player.player_id}`, player, sideLabel });
      }
    });
  };
  pushFrom(mine, 'Your lineup');
  pushFrom(opponent, opponent.team_name);
  return items;
}

function recordLabel(side: MatchupSide): string {
  if (side.wins == null || side.losses == null) return '—';
  return `${side.wins}-${side.losses}${side.ties ? `-${side.ties}` : ''}`;
}

/** Same shape both `MatchupStarter` (suggested) and `MatchupRealStarter`
 * (actual) satisfy — one converter for either lineup's row into PlayerDetail's
 * navigation param, so opening a player detail behaves identically no matter
 * which of the two lineup views the user tapped from. */
function toRankedPlayer(player: MatchupStarter | MatchupRealStarter) {
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

  const { my_team: mine, opponent, comparison, real_comparison: realComparison, week } = matchup;
  const openPlayer = (player: MatchupStarter | MatchupRealStarter) =>
    navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName });

  // Once Sleeper has real live data for BOTH sides, the hero leads with it —
  // that's the direct answer to "what matters right now." Until then, the
  // hero is exactly the season-value comparison it always was.
  const heroEdge = realComparison ? realComparison.edge : comparison.edge;

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <AnimatedCard glow style={styles.headlineCard}>
          <View style={styles.weekRow}>
            <Ionicons name="american-football-outline" size={14} color={colors.accent} />
            <AppText style={styles.weekLabel}>{week != null ? `WEEK ${week}` : 'THIS WEEK'}</AppText>
            {realComparison ? (
              <View style={styles.liveBadge}>
                <View style={styles.liveDot} />
                <AppText style={styles.liveBadgeText}>LIVE</AppText>
              </View>
            ) : null}
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
              <AppText style={[styles.versusValue, { color: edgeColor(colors)[heroEdge === 'you' ? 'you' : 'even'] }]}>
                {realComparison ? realComparison.my_points.toFixed(1) : Math.round(comparison.my_season_value).toLocaleString()}
              </AppText>
              {realComparison ? (
                <AppText style={styles.versusSecondaryValue}>
                  {Math.round(comparison.my_season_value).toLocaleString()} season value
                </AppText>
              ) : null}
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
                style={[styles.versusValue, { color: edgeColor(colors)[heroEdge === 'opponent' ? 'you' : 'even'] }]}
              >
                {realComparison
                  ? realComparison.opponent_points.toFixed(1)
                  : Math.round(comparison.opponent_season_value).toLocaleString()}
              </AppText>
              {realComparison ? (
                <AppText style={styles.versusSecondaryValue}>
                  {Math.round(comparison.opponent_season_value).toLocaleString()} season value
                </AppText>
              ) : null}
            </View>
          </View>

          <ValueSplitBar comparison={comparison} realComparison={realComparison} />

          {realComparison ? (
            <View style={styles.verdictBlock}>
              <View style={styles.verdictHeadlineRow}>
                <Ionicons name={edgeIcon(realComparison.edge)} size={17} color={edgeColor(colors)[realComparison.edge]} />
                <AppText style={[styles.edgeHeadline, { color: edgeColor(colors)[realComparison.edge] }]} numberOfLines={2}>
                  {realHeadline(realComparison)}
                  {realComparison.edge === 'even' ? '' : ` (${realComparison.margin > 0 ? '+' : ''}${realComparison.margin.toFixed(1)})`}
                </AppText>
              </View>
              {/* Rendered straight from the API so this line can never drift
                  into claiming more than the data behind it. */}
              <AppText style={styles.basisLabel}>{realComparison.basis_label}</AppText>
              {/* Season-value comparison stays visible, just folded in as
                  supporting context underneath the live one — never buried. */}
              <AppText style={styles.secondaryBasisLabel}>
                By season value: {comparison.headline}
                {comparison.edge === 'even' ? '' : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
              </AppText>
            </View>
          ) : (
            <View style={styles.verdictBlock}>
              <View style={styles.verdictHeadlineRow}>
                <Ionicons name={edgeIcon(comparison.edge)} size={17} color={edgeColor(colors)[comparison.edge]} />
                <AppText style={[styles.edgeHeadline, { color: edgeColor(colors)[comparison.edge] }]} numberOfLines={2}>
                  {comparison.headline}
                  {comparison.edge === 'even' ? '' : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
                </AppText>
              </View>
              {/* Rendered straight from the API so this line can never drift
                  into claiming more than the data behind it. */}
              <AppText style={styles.basisLabel}>{comparison.basis_label}</AppText>
            </View>
          )}
        </AnimatedCard>

        <RealLineupSection
          title="Your actual lineup this week"
          side={mine}
          onPressPlayer={openPlayer}
          accent={colors.accent}
        />
        <RealLineupSection
          title={`${opponent.team_name}'s actual lineup`}
          side={opponent}
          onPressPlayer={openPlayer}
          accent={colors.violet}
        />

        <InjuryWatchSection mine={mine} opponent={opponent} onPressPlayer={openPlayer} />

        <ScreenInfoNote
          text="The suggested starters below are each roster's best available lineup by season-long value — the same optimal-lineup logic My Team uses, run for your opponent too so the comparison is apples to apples. This is a recommendation, not necessarily the lineup either manager has actually set in Sleeper, and it doesn't account for this week's opponent defenses or weather."
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

function ValueSplitBar({
  comparison,
  realComparison,
}: {
  comparison: MatchupComparison;
  realComparison: MatchupRealComparison | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Mirrors the hero numbers above: the split reflects real live points once
  // both sides have them, else falls back to the season-value split exactly
  // as before.
  const mineValue = realComparison ? realComparison.my_points : comparison.my_season_value;
  const opponentValue = realComparison ? realComparison.opponent_points : comparison.opponent_season_value;
  const total = mineValue + opponentValue;
  const mineShare = total > 0 ? Math.max(0.05, Math.min(0.95, mineValue / total)) : 0.5;
  return (
    <View style={styles.splitBar}>
      <View style={[styles.splitFill, { flex: mineShare, backgroundColor: colors.accent }]} />
      <View style={[styles.splitFill, { flex: 1 - mineShare, backgroundColor: colors.violet }]} />
    </View>
  );
}

/**
 * Compact risk summary — one InsightRow per flagged starter across both
 * lineups, grouped under a single "INJURY WATCH" header exactly like the
 * shared section-header treatment `StarterSection` uses below. Renders
 * nothing when neither lineup has a flagged starter, so a clean matchup
 * never shows an empty alert module (Magna Carta §36).
 */
function InjuryWatchSection({
  mine,
  opponent,
  onPressPlayer,
}: {
  mine: MatchupSide;
  opponent: MatchupSide;
  onPressPlayer: (player: MatchupStarter) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const items = useMemo(() => collectInjuryWatch(mine, opponent), [mine, opponent]);
  if (items.length === 0) return null;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <View style={[styles.sectionAccentBar, { backgroundColor: colors.danger }]} />
        <AppText style={styles.sectionLabel} numberOfLines={1}>
          INJURY WATCH
        </AppText>
      </View>
      <AnimatedCard style={styles.sectionCard}>
        {items.map((item, index) => {
          const { tone } = waiverInjuryDisplay(item.player.injury_status);
          const color = item.player.ruled_out ? colors.danger : tone === 'watch' ? colors.premium : colors.danger;
          return (
            <InsightRow
              key={item.key}
              icon="medkit-outline"
              color={color}
              headline={`${item.player.name ?? 'Unknown player'} — ${item.player.injury_label}`}
              detail={`${item.sideLabel} · ${item.player.position ?? item.player.slot ?? ''}`}
              onPress={() => onPressPlayer(item.player)}
              last={index === items.length - 1}
            />
          );
        })}
      </AnimatedCard>
    </View>
  );
}

/**
 * This roster's REAL current-week lineup — the players Sleeper says are
 * actually starting, each with real points scored so far this week. Distinct
 * component (not a `StarterSection` variant) because the row-level meaning is
 * different enough to warrant its own trailing metric (real points, not a
 * season-value score) and title language ("actual" vs. "suggested") — both
 * still built on the same shared `PlayerIdentityRow` primitive.
 *
 * Renders nothing when Sleeper hasn't populated live data for this roster
 * yet (`has_live_data: false`) — an empty/zero-filled card here would read
 * as a real (if bad) score rather than "no data yet" (Magna Carta §36).
 */
function RealLineupSection({
  title,
  side,
  onPressPlayer,
  accent,
}: {
  title: string;
  side: MatchupSide;
  onPressPlayer: (player: MatchupRealStarter) => void;
  accent: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!side.has_live_data || side.real_starters.length === 0) return null;
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeaderRow}>
        <View style={[styles.sectionAccentBar, { backgroundColor: accent }]} />
        <AppText style={styles.sectionLabel} numberOfLines={1}>
          {title.toUpperCase()}
        </AppText>
        {side.real_points != null ? (
          <AppText style={[styles.sectionTotal, { color: accent }]} numberOfLines={1}>
            {side.real_points.toFixed(1)} PTS
          </AppText>
        ) : null}
      </View>
      <AnimatedCard style={styles.sectionCard}>
        {side.real_starters.map((player, index) => (
          <PlayerIdentityRow
            key={`${side.roster_id}-real-${player.player_id}`}
            playerId={player.player_id}
            name={player.name}
            position={player.position}
            team={player.team}
            tier={player.tier}
            opportunityLabel={player.opportunity_label}
            // Same injury_label/tone rule as the suggested lineup below —
            // IR/PUP/season-ending arrives on `status`, not `injury_status`.
            injuryLabel={player.injury_label}
            injuryTone={waiverInjuryDisplay(player.injury_status).tone}
            trailingValue={player.actual_points != null ? player.actual_points.toFixed(1) : '—'}
            trailingCaption="PTS"
            onPress={() => onPressPlayer(player)}
            showDivider={index < side.real_starters.length - 1}
          />
        ))}
      </AnimatedCard>
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
              // injury_label, not injury_status: IR/PUP/season-ending arrives
              // on `status` with `injury_status` blank. Tone still comes from
              // injury_status/waiverInjuryDisplay so "Questionable" reads as
              // the calmer amber `watch` tone instead of the same red as a
              // genuine Out/IR status (see LineupRow's identical fix in
              // MyTeamScreen.tsx, which flagged this as a Matchup follow-up).
              injuryLabel={player.injury_label}
              ruledOut={player.ruled_out}
              injuryTone={waiverInjuryDisplay(player.injury_status).tone}
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
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: spacing.xs,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.pill,
    backgroundColor: colors.accentMuted,
  },
  liveDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.accent },
  liveBadgeText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.6, color: colors.accent },
  versusRow: { flexDirection: 'row', alignItems: 'flex-start' },
  versusSide: { flex: 1 },
  versusAvatar: { borderWidth: 2, marginBottom: spacing.xs },
  versusTeam: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  versusRecord: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
  versusValue: { fontSize: 22, fontWeight: '800', marginTop: spacing.xs },
  versusSecondaryValue: { fontSize: 11, color: colors.textTertiary, marginTop: 1 },
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
  verdictHeadlineRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  // Deliberately the most prominent text treatment in the hero after the
  // season-value numbers themselves: this line is the direct answer to
  // "how do these two teams compare," so it needs more weight than the
  // ordinary-metadata size (14pt) it shipped at — see brief §2 ("give this
  // verdict slightly more visual prominence than ordinary metadata... it
  // should read like FantasyGM Lab's analysis of the matchup").
  edgeHeadline: { flex: 1, fontSize: 17, fontWeight: '800', letterSpacing: 0.1 },
  basisLabel: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs },
  secondaryBasisLabel: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs / 2 },
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
