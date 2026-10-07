import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import MeterRow, { confidenceLevelFor } from '../components/ConfidenceMeter';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import FAABGuidance from '../components/FAABGuidance';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import QuickActionsGrid, { type QuickAction } from '../components/QuickActionsGrid';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import StorylineSummaryCard from '../components/StorylineSummaryCard';
import TeamAvatar from '../components/TeamAvatar';
import TeamHealthContextBlock, { hasHealthContext } from '../components/TeamHealthContextBlock';
import WeeklyMatchupCard from '../components/WeeklyMatchupCard';
import {
  api,
  type DashboardItem,
  type MatchupResponse,
  type TeamSnapshot,
  type WaiverPriorityAdd,
  type WeeklyRecap,
} from '../lib/api';
import { bestAvailableCardVisual } from '../lib/bestAvailableCardVisual';
import { toUserErrorMessage } from '../lib/errorMessages';
import { setLastLeague } from '../lib/lastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { rankedPlayerFromWaiverPlayer } from '../lib/playerStubs';
import { positionRankPrestige } from '../lib/positionRankPrestige';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { gradients, lightGradients, radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { LinearGradient } from 'expo-linear-gradient';

type Props = NativeStackScreenProps<RootStackParamList, 'LeagueDetail'>;

interface LeagueSummary {
  season: string;
  week: string;
  teamCount: string;
  scoring: string;
}

interface MyTeamInfo {
  teamName: string;
  avatarId: string;
  playerCount: number;
  playerIds: string[];
  rosterId: string;
}

// Same icon/color per destination GmOrb's own "Where to Go" sheet already
// uses for these routes (Matchup/Waivers = success, Teams = violet,
// Alerts = danger) — one semantic mapping app-wide, not a fresh set of
// colors invented for this screen. Matchup and Waivers now also have inline
// compact summaries above (coridian_'s 2026-10 brief), but the full
// Matchup screen (suggested starters, opponent lineup) and full Waivers
// screen (search, filters, Best Available, Stash/Watchlist/FAAB boards)
// have real functionality the compact summaries don't cover, so the nav
// tiles stay. My Team is left out of this grid: it already has its own
// richer strip card below with real roster data, so a plain nav tile for
// the same destination would just be a second, weaker way to do the same
// thing. Recap has no tile here either — the inline Storylines section
// above is its entry point now.
function leagueQuickActions(
  colors: ThemeColors,
): Array<{
  label: string;
  route: 'Matchup' | 'Alerts' | 'Waivers' | 'Teams';
  icon: React.ComponentProps<typeof IconCircle>['name'];
  color: string;
}> {
  return [
    { label: 'Matchup', route: 'Matchup', icon: 'american-football-outline', color: colors.success },
    { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline', color: colors.danger },
    { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', color: colors.success },
    { label: 'Teams', route: 'Teams', icon: 'people-circle-outline', color: colors.violet },
  ];
}

function scoringLabel(scoringSettings: Record<string, unknown> | undefined): string {
  const rec = Number(scoringSettings?.rec ?? 0);
  if (rec >= 1) return 'PPR';
  if (rec > 0) return 'Half PPR';
  return 'Standard';
}

export default function LeagueDetailScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [summary, setSummary] = useState<LeagueSummary | null>(null);
  const [dashboardItems, setDashboardItems] = useState<DashboardItem[]>([]);
  const [dashboardQuiet, setDashboardQuiet] = useState(false);
  const [teamSnapshot, setTeamSnapshot] = useState<TeamSnapshot | null>(null);
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [recap, setRecap] = useState<WeeklyRecap | null>(null);
  const [priorityAdds, setPriorityAdds] = useState<WaiverPriorityAdd[]>([]);
  const [myTeam, setMyTeam] = useState<MyTeamInfo | null>(null);
  const [myPlayoffOdds, setMyPlayoffOdds] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'League Overview', leagueName);

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

  useEffect(() => {
    void setLastLeague({ leagueId, leagueName });
  }, [leagueId, leagueName]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        try {
          const [
            leagueResult,
            dashboardResult,
            myRosterResult,
            profilesResult,
            recapResult,
            playoffOddsResult,
            waiversResult,
          ] = await Promise.all([
            api.getLeague(leagueId).catch(() => null),
            api.getLeagueDashboard(leagueId).catch(() => null),
            api.getMyRoster(leagueId).catch(() => null),
            api.getLeagueTeamProfiles(leagueId).catch(() => null),
            api.getLeagueRecap(leagueId).catch(() => null),
            api.getLeaguePlayoffOdds(leagueId).catch(() => null),
            api.getLeagueWaivers(leagueId).catch(() => null),
          ]);
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

          if (dashboardResult) {
            setDashboardItems(dashboardResult.items ?? []);
            setDashboardQuiet(dashboardResult.quiet);
            setTeamSnapshot(dashboardResult.team_snapshot);
          }

          const roster = myRosterResult?.roster as { roster_id?: unknown; players?: unknown } | null | undefined;
          let rosterIdForOdds = '';
          if (roster && profilesResult) {
            const rosterId = String(roster.roster_id ?? '');
            rosterIdForOdds = rosterId;
            const profile = profilesResult.profiles[rosterId];
            const playerIds = Array.isArray(roster.players) ? roster.players.map(String) : [];
            setMyTeam({
              teamName: profile?.team_name || 'Your team',
              avatarId: profile?.avatar_id || '',
              playerCount: playerIds.length,
              playerIds,
              rosterId,
            });
          }

          if (recapResult?.recap && !recapResult.recap.incomplete) {
            setRecap(recapResult.recap);
          }

          if (waiversResult) {
            setPriorityAdds(waiversResult.priority_adds ?? []);
          }

          if (rosterIdForOdds && playoffOddsResult && !playoffOddsResult.reason) {
            const myOdds = playoffOddsResult.teams.find((team) => String(team.roster_id) === rosterIdForOdds);
            if (myOdds) setMyPlayoffOdds(myOdds.playoff_probability);
          }
        } catch (err) {
          if (!cancelled) {
            setError(toUserErrorMessage(err, 'Failed to load league.'));
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      void load();
      // Independent, best-effort — the matchup card is an entry point, not
      // core to the page load above, so a bye week or a league without a
      // current week simply means no card rather than an error state for
      // the rest of the screen (same contract as Next Move's own matchup
      // fetch in DashboardScreen).
      api
        .getLeagueMatchup(leagueId)
        .then((result) => {
          if (!cancelled) setMatchup(result);
        })
        .catch(() => {});
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

  const heroHeadline = dashboardQuiet || dashboardItems.length === 0
    ? 'Quiet week — nothing urgent'
    : `${dashboardItems.length} priority move${dashboardItems.length === 1 ? '' : 's'} identified`;
  const heroSubtitle = dashboardItems[0]?.headline ?? 'Your roster looks steady right now.';

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.list} contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text={`League Overview is home base for ${leagueName} — your matchup, injury concerns, storylines, and waiver suggestions, plus quick access to everything else. For the full personalized briefing, see Next Move.`}
      />

      {/* DOMINANT MODULE — the matchup leads the page per coridian_'s
          2026-10 brief ("at the very top should be the matchup"). Everything
          below supports it: injury concerns, storylines, waiver suggestions,
          then the Today's Game Plan entry point and the rest of this
          screen's nav/context (UI_HIERARCHY_DIRECTIVE §6's "one dominant
          module per screen" — this explicit, page-specific instruction
          supersedes that directive's own §19 example for this screen, same
          as mobile/AGENTS.md's "page-specific prompts... may change
          composition and information hierarchy" clause allows). */}
      {matchup ? (
        <WeeklyMatchupCard
          matchup={matchup}
          glow
          onPress={() => navigation.navigate('Matchup', { leagueId, leagueName })}
        />
      ) : null}

      {/* Injury concerns — same already-computed team-health read Next
          Move's Needs Attention group shows, promoted into its own section
          here per coridian_'s brief. */}
      {hasHealthContext(teamSnapshot) ? (
        <View style={styles.groupSection}>
          <SectionHeading title="Injury Concerns" icon="pulse-outline" />
          <AnimatedCard style={styles.groupCard}>
            <TeamHealthContextBlock
              snapshot={teamSnapshot!}
              last
              onPlayerPress={(player) =>
                navigation.navigate('PlayerDetail', {
                  player: {
                    player_id: player.player_id,
                    name: player.name || null,
                    position: player.position || null,
                    team: player.team || null,
                    age: null,
                    status: null,
                    injury_status: player.injury_status || null,
                    tier: player.tier || null,
                    score: player.player_value_score,
                    overall_rank: null,
                    position_rank: null,
                    rank_unavailable_reason: null,
                    opportunity_label: null,
                  },
                  leagueId,
                  leagueName,
                })
              }
            />
          </AnimatedCard>
        </View>
      ) : null}

      {/* Storylines — this week's recap headline + top stories. Absorbs the
          old standalone "Week N recap ready" strip card (see Feature
          Parity note in the PR description): same destination, richer
          inline preview. */}
      {recap ? (
        <View style={styles.groupSection}>
          <SectionHeading title="Storylines" icon="newspaper-outline" />
          <StorylineSummaryCard recap={recap} onPress={() => navigation.navigate('Recap', { leagueId, leagueName })} />
        </View>
      ) : null}

      {/* Waiver suggestions — the same Priority Adds the Waivers screen
          surfaces, condensed into a horizontal strip of small square
          player cards (coridian_, Discord: "small player cards. Square,
          border is prestige, overall top right, name bottom, and anything
          else pertinent can be sprinkled on somehow") — the same prestige
          glow-border/OVR-top-right/name-bottom treatment Waivers' Best
          Available cards use (see WaiversScreen.tsx's BestAvailableCard,
          PR #889), applied to this screen's own condensed preview. Always
          capped at 3 (slice below), so a horizontal strip never needs to
          scroll on a normal phone width — same row pattern as Best
          Available rather than a 2-column grid, for visual consistency
          with that other square-card list. */}
      {priorityAdds.length > 0 ? (
        <View style={styles.groupSection}>
          <SectionHeading title="Waiver Suggestions" icon="swap-horizontal-outline" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.suggestionRow}>
            {priorityAdds.slice(0, 3).map((player) => (
              <WaiverSuggestionCard
                key={player.player_id}
                player={player}
                onPress={() =>
                  navigation.navigate('PlayerDetail', {
                    player: rankedPlayerFromWaiverPlayer(player),
                    leagueId,
                    leagueName,
                  })
                }
              />
            ))}
          </ScrollView>
        </View>
      ) : null}

      {/* Entry point to the full Next Move briefing — demoted from its old
          "first card on the page" position now that the matchup leads, but
          still present (feature parity) one tap away. */}
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={() => navigation.navigate('Dashboard', { leagueId, leagueName })}
      >
        <LinearGradient colors={isDark ? gradients.hero : lightGradients.hero} style={styles.heroCard}>
          <AppText style={styles.heroKicker}>TODAY'S GAME PLAN</AppText>
          <AppText style={styles.heroHeadline}>{heroHeadline}</AppText>
          <AppText style={styles.heroSubtitle} numberOfLines={1}>
            {heroSubtitle}
          </AppText>
          <View style={styles.heroButton}>
            <AppText style={styles.heroButtonText}>View Plan</AppText>
          </View>
        </LinearGradient>
      </TouchableOpacity>

      {summary ? (
        <View style={styles.contextRow}>
          <Ionicons name="calendar-outline" size={13} color={colors.textTertiary} />
          <AppText style={styles.contextText}>
            {summary.season} · Week {summary.week} · {summary.teamCount} teams · {summary.scoring}
          </AppText>
        </View>
      ) : null}

      <QuickActionsGrid
        actions={leagueQuickActions(colors).map(
          (action): QuickAction => ({
            key: action.route,
            label: action.label,
            icon: action.icon,
            color: action.color,
            onPress: () => navigation.navigate(action.route, { leagueId, leagueName }),
          }),
        )}
      />

      {myTeam ? (
        <AnimatedCard
          style={styles.stripCard}
          onPress={() =>
            navigation.navigate('TeamRoster', {
              ownerName: myTeam.teamName,
              playerIds: myTeam.playerIds,
              leagueId,
              leagueName,
              rosterId: myTeam.rosterId,
            })
          }
        >
          <TeamAvatar avatarId={myTeam.avatarId} size={36} style={styles.stripAvatar} />
          <View style={styles.stripTextGroup}>
            <View style={styles.stripNameRow}>
              <AppText style={styles.stripName} numberOfLines={1}>
                {myTeam.teamName}
              </AppText>
              <View style={styles.youBadge}>
                <AppText style={styles.youBadgeText}>You</AppText>
              </View>
            </View>
          </View>
          <AppText style={styles.stripValue}>{myTeam.playerCount}</AppText>
          <AppText style={styles.stripValueLabel}>PLAYERS</AppText>
        </AnimatedCard>
      ) : null}

      {myPlayoffOdds !== null ? (
        <AnimatedCard
          style={styles.stripCard}
          onPress={() => navigation.navigate('PlayoffOdds', { leagueId, leagueName })}
        >
          <IconCircle name="podium-outline" color={colors.violet} size={36} />
          <AppText style={styles.stripTextGroup2}>
            Your simulated playoff odds: {Math.round(myPlayoffOdds)}%
          </AppText>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </AnimatedCard>
      ) : null}
      </ScrollView>
    </View>
  );
}

/**
 * Small square "Waiver Suggestions" card for League Overview — same
 * prestige-tier glow border / "GOLD"/"SILVER"/"BRONZE" label / OVR-top-right
 * / name-bottom-center treatment as Waivers' `BestAvailableCard` (PR #889),
 * reusing `positionRankPrestige` + `bestAvailableCardVisual` unmodified:
 * `WaiverPriorityAdd` extends `WaiverPlayer`, so it carries the exact same
 * wire-relative free-agent-pool `position_rank` Best Available already
 * feeds through that same tier decision — this is the same real prestige
 * signal, not a fabricated one, and an untiered player still gets the
 * plain neutral card with no glow, same restraint rule.
 *
 * The large value number this screen's old compact row showed (e.g.
 * "4432") is `player.score` — a wire-relative ranking score, not a 0-99
 * rating — so it does not belong in the OVR slot. `OverallRatingBadge`
 * above instead gets `player.overall_rating` (the real 0-99-scale field,
 * same one Best Available's own badge uses) + `player.position_rank`, the
 * same pairing that badge already expects everywhere else in the app.
 *
 * "Anything else pertinent, sprinkled on": FAAB bid guidance (the $ range
 * this screen's old compact row already showed) and the recommendation's
 * CONFIDENCE meter — the two most decision-relevant facts beyond identity
 * and value, and the same signals this screen's "condensed... top couple
 * of compact rows" already surfaced. Dropped from this condensed card —
 * team code, the tier text chip (the avatar ring still carries tier
 * color), injury pill, Sleeper trending pill, the recommendation-type
 * pill, and the separate "Full breakdown" text link — all still render on
 * the Waivers tab's own Priority Adds list (`WaiverRecommendationCard`'s
 * `compact` variant, unchanged) and on Player Detail, one tap away; this
 * card was already a condensed preview, not the authoritative place for
 * that detail, matching Best Available's own precedent of dropping the
 * same fields from its square card. The whole card is now the tap target
 * (-> Player Detail), replacing the separate "Full breakdown" link per the
 * product-owner's "whatever else" instruction to keep this dense without
 * overcrowding it.
 */
function WaiverSuggestionCard({ player, onPress }: { player: WaiverPriorityAdd; onPress: () => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const prestige = positionRankPrestige(player.position_rank, isDark);
  const visual = bestAvailableCardVisual(prestige.tier);
  return (
    <AnimatedCard
      style={styles.suggestionCard}
      onPress={onPress}
      glow={visual.glow}
      glowColor={prestige.color ?? undefined}
    >
      <View style={styles.suggestionTopRow}>
        {visual.prestigeLabel ? (
          <AppText style={[styles.suggestionPrestigeLabel, { color: prestige.color ?? colors.textTertiary }]}>
            {visual.prestigeLabel}
          </AppText>
        ) : (
          <View />
        )}
        <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
      </View>
      <PlayerAvatar playerId={player.player_id} size={40} tier={player.tier} style={styles.suggestionAvatar} />
      <View style={styles.suggestionPosBadgeWrap}>
        <PositionBadge position={player.position} size="sm" />
      </View>
      <AppText style={styles.suggestionName} numberOfLines={1}>
        {player.name ?? 'Unknown'}
      </AppText>
      <View style={styles.suggestionFooter}>
        <FAABGuidance faab={player.faab} size="compact" />
        {player.confidence_label ? (
          <MeterRow
            label="CONFIDENCE"
            value={player.confidence_label}
            level={confidenceLevelFor(player.confidence_label)}
            color={colors.premium}
          />
        ) : null}
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  list: { backgroundColor: 'transparent' },
  listContent: { padding: spacing.lg, paddingBottom: spacing.xl * 3, gap: spacing.md },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  heroCard: {
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    minHeight: 132,
  },
  heroKicker: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.8 },
  heroHeadline: { fontSize: 20, fontWeight: '700', color: colors.textPrimary, marginTop: 4 },
  heroSubtitle: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
  heroButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    marginTop: spacing.md,
  },
  heroButtonText: { fontSize: 12, fontWeight: '700', color: colors.background },
  // Shared "grouped surface" wrapper for Injury Concerns / Waiver
  // Suggestions — a SectionHeading over one AnimatedCard, matching Next
  // Move's own Needs Attention/Opportunities grouped-surface pattern
  // (Magna Carta §12: one card with internal dividers, not card-per-item).
  groupSection: {},
  groupCard: { padding: spacing.lg, paddingVertical: spacing.xs },
  // Waiver Suggestions' small square cards — same horizontal-strip
  // container pattern as Waivers' own bestAvailableRow.
  suggestionRow: { flexDirection: 'row', gap: spacing.sm, paddingRight: spacing.lg },
  // Wider than Waivers' 124pt bestAvailableCard — this card additionally
  // carries FAAB guidance + a CONFIDENCE meter, both reused unmodified from
  // their existing shared components, so the card needs enough width for
  // MeterRow's label/segments/value to sit on one line without wrapping.
  suggestionCard: { width: 184, padding: spacing.sm, alignItems: 'center', gap: 2 },
  // Prestige label (left) <-> OVR badge (right) — same spacer-view/minHeight
  // trick as Waivers' bestAvailableTopRow so every card in the strip lines
  // up the same whether or not it has a prestige tier.
  suggestionTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    alignSelf: 'stretch',
    minHeight: 14,
    marginBottom: spacing.xs,
  },
  suggestionPrestigeLabel: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  suggestionAvatar: { marginTop: 2 },
  suggestionPosBadgeWrap: { alignSelf: 'center', marginTop: spacing.xs },
  // The card's most visually dominant text (UI_HIERARCHY_DIRECTIVE.md §11)
  // — larger/bolder than the prestige label and OVR badge above it, same
  // 15/800 treatment as Waivers' bestAvailableName.
  suggestionName: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, marginTop: spacing.xs },
  suggestionFooter: { alignSelf: 'stretch', alignItems: 'center', gap: 4, marginTop: spacing.xs },
  contextRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  contextText: { fontSize: 12, fontWeight: '500', color: colors.textSecondary, letterSpacing: 0.2 },
  stripCard: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md, gap: spacing.sm },
  stripAvatar: {},
  stripTextGroup: { flex: 1 },
  stripNameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  stripName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  youBadge: { backgroundColor: colors.accent, borderRadius: radii.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  youBadgeText: { color: colors.background, fontSize: 10, fontWeight: '700' },
  stripValue: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  stripValueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, marginLeft: 4 },
  stripTextGroup2: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
