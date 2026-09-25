import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnalyticsSection from '../components/AnalyticsSection';
import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import CircularProgressRing from '../components/CircularProgressRing';
import GridBackground from '../components/GridBackground';
import MetricCard from '../components/MetricCard';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAnalysisPanel, { hasRosterAnalysis } from '../components/TeamAnalysisPanel';
import TeamAvatar from '../components/TeamAvatar';
import { waiverInjuryDisplay } from '../components/WaiverRecommendationCard';
import { api, type LineupPlayer, type TeamRanking } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { percentileColor, percentileFromRank } from '../lib/percentile';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
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

// Same three buckets PlayersScreen.tsx's own age filter already uses
// (AGE_FILTERS: Under 25 / 25-28 / 29+) — reused here rather than inventing
// a second set of age thresholds for the same underlying concept.
function ageLabel(averageAge: number | null): string {
  if (averageAge == null) return '—';
  if (averageAge < 25) return 'Young';
  if (averageAge <= 28) return 'Prime';
  return 'Aging';
}

/**
 * My Team's local subnav — coridian_'s "roster command center" brief:
 * Overview (identity/value + a condensed starters preview), Starters (full
 * lineup + a real aggregate), Bench (full bench, visually quieter), Analysis
 * (the real TeamRanking rank matrix + archetype narrative, via
 * TeamAnalysisPanel). Keeps every roster concept reachable without forcing
 * Team Snapshot + Starters + Bench + Analysis into one endless scroll — see
 * SegmentedTabBar (built for Player Detail's Stats/Trends/... tabs), reused
 * here rather than a My-Team-specific tab control.
 */
type TeamTab = 'overview' | 'starters' | 'bench' | 'analysis';

const TEAM_TABS: Array<{ key: TeamTab; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'starters', label: 'Starters' },
  { key: 'bench', label: 'Bench' },
  { key: 'analysis', label: 'Analysis' },
];

function infoNoteText(tab: TeamTab, leagueName: string): string {
  switch (tab) {
    case 'starters':
      return `Your suggested starting lineup for ${leagueName} — the same optimal-lineup logic the web app's Dashboard and My Team pages use.`;
    case 'bench':
      return `Every other rostered player in ${leagueName} not currently in your suggested starting lineup.`;
    case 'analysis':
      return `Real roster analytics for ${leagueName} — the same team-evaluation model used across FantasyGM Lab.`;
    default:
      return `Your roster snapshot for ${leagueName} — strength, identity, and starting lineup at a glance.`;
  }
}

export default function MyTeamScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [starters, setStarters] = useState<LineupPlayer[]>([]);
  const [bench, setBench] = useState<LineupPlayer[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [myTeam, setMyTeam] = useState<TeamRanking | null>(null);
  const [leagueSize, setLeagueSize] = useState(0);
  const [activeTab, setActiveTab] = useState<TeamTab>('overview');

  useScreenHeaderTitle(navigation, 'My Team', leagueName);

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
          const result = await api.getLeagueMyTeam(leagueId);
          if (cancelled) return;
          setStarters(result.starters);
          setBench(result.bench);
          setNotice(result.reason ? reasonMessage(result.reason) : null);
          // Best-effort, independent of the lineup fetch above — Team
          // Analytics is a bonus section, not core to this screen, so a
          // failure here shouldn't block showing the lineup.
          if (result.roster_id) {
            api
              .getLeagueTeamRankings(leagueId)
              .then((rankings) => {
                if (cancelled) return;
                setLeagueSize(rankings.teams.length);
                setMyTeam(rankings.teams.find((team) => team.roster_id === result.roster_id) ?? null);
              })
              .catch(() => {});
          }
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

  const totalStartersValue = useMemo(
    () => starters.reduce((sum, player) => sum + (player.score ?? 0), 0),
    [starters],
  );

  const goToPlayer = useCallback(
    (player: LineupPlayer) => {
      navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName });
    },
    [navigation, leagueId, leagueName],
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

  if (notice) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notice}>{notice}</AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <View style={styles.tabBar}>
          <SegmentedTabBar options={TEAM_TABS} active={activeTab} onChange={setActiveTab} />
        </View>
        <ScreenInfoNote text={infoNoteText(activeTab, leagueName)} />

        {activeTab === 'overview' ? (
          <>
            {myTeam ? (
              <TeamAnalyticsSection
                team={myTeam}
                leagueSize={leagueSize}
                onViewAnalysis={hasRosterAnalysis(myTeam) ? () => setActiveTab('analysis') : undefined}
              />
            ) : null}
            {starters.length > 0 ? (
              <StartersPreviewSection
                starters={starters}
                totalValue={totalStartersValue}
                onPressPlayer={goToPlayer}
                onViewAll={() => setActiveTab('starters')}
              />
            ) : null}
          </>
        ) : null}

        {activeTab === 'starters' ? (
          <StartersFullSection starters={starters} totalValue={totalStartersValue} onPressPlayer={goToPlayer} />
        ) : null}

        {activeTab === 'bench' ? <BenchFullSection bench={bench} onPressPlayer={goToPlayer} /> : null}

        {activeTab === 'analysis' ? (
          myTeam ? (
            <TeamAnalysisPanel
              team={myTeam}
              leagueSize={leagueSize}
              onOpenTeams={() => navigation.navigate('Teams', { leagueId, leagueName })}
            />
          ) : (
            <EmptyState
              icon="stats-chart-outline"
              title="Analysis unavailable"
              subtitle="Team analytics aren't available for this roster right now."
            />
          )
        ) : null}
      </ScrollView>
    </View>
  );
}

/**
 * The concept sheet's Panel 4 ("MY TEAM") leads with a team-value ring plus
 * a Key Metrics readout — this screen had no equivalent team-level summary
 * at all before, only the lineup. Every number here is real: Team Value,
 * Starter Strength and Draft Capital are percentiles derived from
 * modules/league_rankings.py's own dense ranks (best team in the league ->
 * 100), Roster Age is the real average, and Overall Outlook is the
 * archetype/strategy label modules/team_eval.py already assigns per roster.
 * Two panel-7 items ("Contender Window", a multi-year projected/ceiling/
 * floor chart) are deliberately NOT here — nothing in the backend computes
 * either, and showing invented numbers next to real ones would be worse
 * than showing nothing.
 *
 * Built on the same MetricCard/AnalyticsSection primitives Dashboard's
 * League Snapshot and Player Detail's Stats tab use (rather than this
 * screen's own icon-cell grid + a second, page-local percentile bar), so
 * "how good is this number" reads through one shared percentile scale
 * (lib/percentile.ts) everywhere in the app instead of two. Draft Capital
 * previously appeared twice — once as an icon cell, once as a percentile
 * bar — collapsed here into the single MetricCard tile.
 *
 * `onViewAnalysis`, when provided, renders a compact "View Analysis" link
 * into the card's own header row, next to the "Team Snapshot" title
 * (matching coridian_'s concept mockup exactly) — only ever passed when
 * TeamAnalysisPanel actually has real content to show (see
 * `hasRosterAnalysis`), never as a dead affordance.
 */
/** Young/Prime/Aging isn't itself good/bad, but Prime is the ideal state,
 * Aging carries real roster risk, and Young is still "not there yet" —
 * distinct from a plain percentile tier, so this stays a page-local
 * mapping rather than being forced through the shared percentile ramp. */
function ageColor(averageAge: number | null, colors: ThemeColors): string {
  if (averageAge == null) return colors.textTertiary;
  if (averageAge <= 28) return colors.success;
  if (averageAge <= 30) return colors.premium;
  return colors.danger;
}

function TeamAnalyticsSection({
  team,
  leagueSize,
  onViewAnalysis,
}: {
  team: TeamRanking;
  leagueSize: number;
  onViewAnalysis?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const valuePercentile = percentileFromRank(team.power_rank, leagueSize);
  const draftCapitalPercentile = percentileFromRank(team.draft_capital_rank, leagueSize);
  const starterPercentile = percentileFromRank(team.starter_rank, leagueSize);
  const outlook = team.archetype_label || team.strategy_label;
  const ringColor = valuePercentile != null ? percentileColor(valuePercentile, colors) : colors.accent;

  return (
    <AnalyticsSection
      title="Team Snapshot"
      icon="bar-chart-outline"
      footer={onViewAnalysis ? <HeaderLink label="View Analysis" onPress={onViewAnalysis} /> : undefined}
    >
      <View style={styles.analyticsHeaderRow}>
        <View style={styles.analyticsRingWrap}>
          <CircularProgressRing
            percent={valuePercentile ?? 0}
            size={84}
            strokeWidth={8}
            color={ringColor}
            valueLabel={valuePercentile != null ? String(valuePercentile) : '—'}
          />
          <AppText style={styles.analyticsRingCaption}>TEAM VALUE</AppText>
        </View>
        {team.avatar_url ? (
          <TeamAvatar avatarId={team.avatar_url} size={52} style={styles.analyticsTeamAvatar} />
        ) : null}
        <View style={styles.analyticsHeaderText}>
          {outlook ? (
            <View style={styles.outlookBadge}>
              <AppText style={styles.outlookBadgeText}>{outlook.toUpperCase()}</AppText>
            </View>
          ) : null}
          {team.power_rank != null ? (
            <AppText style={styles.analyticsRankLine}>
              Power Rank #{team.power_rank} of {leagueSize}
            </AppText>
          ) : null}
        </View>
      </View>
      <View style={styles.analyticsMetricsRow}>
        <MetricCard
          label="Starter Strength"
          value={team.starter_rank != null ? `#${team.starter_rank}` : '—'}
          percentile={starterPercentile}
          valueColor={starterPercentile != null ? percentileColor(starterPercentile, colors) : undefined}
          style={styles.analyticsMetricTile}
        />
        <MetricCard
          label="Draft Capital"
          value={team.draft_capital_rank != null ? `#${team.draft_capital_rank}` : '—'}
          percentile={draftCapitalPercentile}
          valueColor={draftCapitalPercentile != null ? percentileColor(draftCapitalPercentile, colors) : undefined}
          style={styles.analyticsMetricTile}
        />
        <MetricCard
          label="Roster Age"
          value={team.average_age != null ? team.average_age.toFixed(1) : '—'}
          note={ageLabel(team.average_age)}
          valueColor={ageColor(team.average_age, colors)}
          style={styles.analyticsMetricTile}
        />
      </View>
    </AnalyticsSection>
  );
}

/**
 * Overview's "condensed preview" (brief §2): the first few starters plus a
 * link into the full Starters tab, instead of always rendering the entire
 * lineup on Overview too — the full list (with its own aggregate) lives on
 * the Starters tab so Overview stays a quick glance, not a second copy of
 * the same long list. Header row now also carries the real "Total Starters
 * Value" aggregate (concept mockup shows this directly under Team Snapshot,
 * on the Overview tab itself, not only once a user drills into the full
 * Starters tab) — same `totalStartersValue` sum MyTeamScreen already
 * computes for the Starters tab, just surfaced here too.
 */
function StartersPreviewSection({
  starters,
  totalValue,
  onPressPlayer,
  onViewAll,
}: {
  starters: LineupPlayer[];
  totalValue: number;
  onPressPlayer: (player: LineupPlayer) => void;
  onViewAll: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const preview = starters.slice(0, 3);
  return (
    <View>
      <SectionHeaderRow label="Starters" total={formatTotalStartersValue(totalValue)} />
      <AnimatedCard style={styles.groupCard}>
        {preview.map((player, index) => (
          <LineupRow
            key={player.player_id}
            player={player}
            showDivider={index < preview.length - 1}
            onPress={() => onPressPlayer(player)}
          />
        ))}
        <LinkRow label={`View all ${starters.length} Starters`} onPress={onViewAll} />
      </AnimatedCard>
    </View>
  );
}

/** "Total Starters Value 48,123" — label-then-number, matching coridian_'s
 * concept mockup exactly (previously rendered as "48,123 TOTAL VALUE",
 * number-then-label). Shared by the Overview preview header and the full
 * Starters tab header so the two never drift into two different phrasings
 * of the same real aggregate. */
function formatTotalStartersValue(totalValue: number): string | null {
  return totalValue > 0 ? `Total Starters Value ${Math.round(totalValue).toLocaleString()}` : null;
}

/**
 * Section 7: a real "Total Starters Value" aggregate — the sum of the exact
 * per-starter `score` values already rendered in each row below, never a
 * fabricated number the app has no inputs for.
 */
function StartersFullSection({
  starters,
  totalValue,
  onPressPlayer,
}: {
  starters: LineupPlayer[];
  totalValue: number;
  onPressPlayer: (player: LineupPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View>
      <SectionHeaderRow label="Starters" total={formatTotalStartersValue(totalValue)} />
      {starters.length === 0 ? (
        <EmptyState icon="people-outline" title="No suggested starters yet." />
      ) : (
        <AnimatedCard style={styles.groupCard}>
          {starters.map((player, index) => (
            <LineupRow
              key={player.player_id}
              player={player}
              showDivider={index < starters.length - 1}
              onPress={() => onPressPlayer(player)}
            />
          ))}
        </AnimatedCard>
      )}
    </View>
  );
}

/**
 * Bench keeps the exact same PlayerIdentityRow family and roster structure
 * (brief §14 — never remove bench players), just a touch quieter than
 * Starters: the trailing value number drops from the cyan accent to a plain
 * secondary tone so cyan stays reserved for the roster's actual starting
 * value (Magna Carta §2 — "cyan second"), not a completely different row
 * design.
 *
 * Split into up to three grouped cards — plain Bench, Injured Reserve, Taxi
 * Squad — using the server's real Sleeper `roster_slot` (see
 * LineupPlayer.roster_slot), not `injury_label`: a healthy player can be
 * parked on IR just as easily as an actually-hurt one can sit in a plain
 * bench slot, so this is strictly "where the manager placed them," kept
 * distinct from the injury tag each row already renders via LineupRow.
 * Reuses the same SectionHeaderRow/sectionLabel/AnimatedCard/LineupRow
 * building blocks as the rest of this screen rather than a new pattern —
 * an IR/Taxi group with nothing in it simply doesn't render.
 */
function BenchFullSection({
  bench,
  onPressPlayer,
}: {
  bench: LineupPlayer[];
  onPressPlayer: (player: LineupPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const activeBench = bench.filter((p) => p.roster_slot !== 'ir' && p.roster_slot !== 'taxi');
  const irBench = bench.filter((p) => p.roster_slot === 'ir');
  const taxiBench = bench.filter((p) => p.roster_slot === 'taxi');
  return (
    <View>
      <SectionHeaderRow label="Bench" />
      {bench.length === 0 ? (
        <EmptyState icon="people-outline" title="No bench players." />
      ) : (
        <>
          {activeBench.length > 0 ? (
            <AnimatedCard style={styles.groupCard}>
              {activeBench.map((player, index) => (
                <LineupRow
                  key={player.player_id}
                  player={player}
                  showDivider={index < activeBench.length - 1}
                  onPress={() => onPressPlayer(player)}
                  muted
                />
              ))}
            </AnimatedCard>
          ) : null}
          {irBench.length > 0 ? (
            <BenchSlotGroup label="Injured Reserve" players={irBench} onPressPlayer={onPressPlayer} />
          ) : null}
          {taxiBench.length > 0 ? (
            <BenchSlotGroup label="Taxi Squad" players={taxiBench} onPressPlayer={onPressPlayer} />
          ) : null}
        </>
      )}
    </View>
  );
}

function BenchSlotGroup({
  label,
  players,
  onPressPlayer,
}: {
  label: string;
  players: LineupPlayer[];
  onPressPlayer: (player: LineupPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View>
      <AppText style={styles.sectionLabel}>{label}</AppText>
      <AnimatedCard style={styles.groupCard}>
        {players.map((player, index) => (
          <LineupRow
            key={player.player_id}
            player={player}
            showDivider={index < players.length - 1}
            onPress={() => onPressPlayer(player)}
            muted
          />
        ))}
      </AnimatedCard>
    </View>
  );
}

function SectionHeaderRow({ label, total }: { label: string; total?: string | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.sectionHeaderRow}>
      <AppText style={styles.sectionHeaderLabel}>{label}</AppText>
      {total ? <AppText style={styles.sectionTotal}>{total}</AppText> : null}
    </View>
  );
}

/** One shared "go deeper" affordance (icon-free text + chevron, top hairline
 * to read as a natural extension of the surface above it) — backs the
 * Starters preview's "View all N Starters", instead of a one-off tappable
 * text style. */
function LinkRow({ label, onPress }: { label: string; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity style={styles.linkRow} onPress={onPress} activeOpacity={0.7}>
      <AppText style={styles.linkRowText}>{label}</AppText>
      <Ionicons name="chevron-forward" size={14} color={colors.accent} />
    </TouchableOpacity>
  );
}

/** Same tappable text-plus-chevron affordance as `LinkRow`, but borderless
 * and untethered from block flow — for sitting inline inside a card's own
 * header row (`AnalyticsSection`'s `footer` slot) next to the section
 * title, e.g. Team Snapshot's "View Analysis" in coridian_'s concept
 * mockup, rather than as a separate row beneath the card's content. */
function HeaderLink({ label, onPress }: { label: string; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity style={styles.headerLink} onPress={onPress} activeOpacity={0.7} hitSlop={6}>
      <AppText style={styles.linkRowText}>{label}</AppText>
      <Ionicons name="chevron-forward" size={13} color={colors.accent} />
    </TouchableOpacity>
  );
}

/**
 * One roster row — canonical PlayerIdentityRow for identity plus a trailing
 * Value/OVR column, matching TeamRosterScreen's RosterPlayerRow exactly
 * (Magna Carta §19, §47) rather than a third bespoke player-row layout.
 *
 * Injury severity: `injury_label`/`ruled_out` stay server-resolved (IR/PUP
 * arrives on `status` with `injury_status` blank — see LineupPlayer's own
 * doc comment — and `ruled_out` already encodes the roster-context nuance
 * of "kept as a starter because nothing else was available"), but the
 * risk-vs-watch *tone* is derived the same way Waivers/Players/GmTargets/
 * TeamRoster already derive it (`waiverInjuryDisplay`) instead of always
 * defaulting to the harsher 'risk' red. Brief §12 asks specifically whether
 * an injury pill and a red-toned tier badge (IMPACT STARTER) could read as
 * the same thing: PlayerIdentityRow's TierBadge is a bordered, translucent
 * chip in the meta row and the injury pill is a borderless solid chip in
 * the name row (different shape, different row, different hex — EF4444 vs
 * FF4D4D dark / B91C1C vs D92D2D light) so they were already visually
 * distinct; the real gap here was "Questionable" always rendering in the
 * same red family as a genuine Out/IR status instead of the calmer amber
 * `watch` tone the semantic color system calls for. MatchupScreen's
 * lineup rows share this exact LineupPlayer shape and have the identical
 * gap — worth the same fix there in a follow-up pass.
 */
function LineupRow({
  player,
  onPress,
  showDivider,
  muted = false,
}: {
  player: LineupPlayer;
  onPress: () => void;
  showDivider: boolean;
  muted?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injuryTone = waiverInjuryDisplay(player.injury_status).tone;
  return (
    <TouchableOpacity
      style={[styles.compactRow, showDivider && styles.compactDivider]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.compactIdentity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          slot={player.slot === 'BENCH' ? player.position : player.slot}
          opportunityLabel={player.opportunity_label}
          // injury_label, not injury_status: IR/PUP/season-ending arrives on
          // `status` with `injury_status` blank, and an injury_status-driven
          // pill hides exactly those players. See LineupPlayer.injury_label.
          injuryLabel={player.injury_label}
          ruledOut={player.ruled_out}
          injuryTone={injuryTone}
          showDivider={false}
        />
      </View>
      <View style={styles.valueColumn}>
        <AppText style={[styles.valueNumber, muted && styles.valueNumberMuted]}>
          {player.score != null ? Math.round(player.score) : '—'}
        </AppText>
        <AppText style={styles.valueLabel}>VALUE</AppText>
        <OverallRatingBadge rating={player.overall_rating} />
      </View>
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  tabBar: { marginBottom: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginBottom: spacing.md },
  analyticsHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  analyticsRingWrap: { alignItems: 'center' },
  analyticsRingCaption: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.5,
    marginTop: spacing.xs,
  },
  analyticsTeamAvatar: { borderWidth: 2, borderColor: colors.accent },
  analyticsHeaderText: { flex: 1, gap: spacing.xs },
  // Solid cyan fill + near-black text, matching coridian_'s concept mockup
  // exactly (a translucent accentMuted chip with cyan text read as a plain
  // outline pill there, not the bold filled badge the concept shows) — same
  // solid-accent-pill pattern LeagueDetailScreen's "YOU" badge already uses
  // (Magna Carta §3: cyan = GM intelligence/analytical emphasis, at its
  // strongest here since the archetype label is this card's headline call-out).
  outlookBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: 4,
  },
  outlookBadgeText: { fontSize: 11, fontWeight: '800', color: colors.background, letterSpacing: 0.4 },
  analyticsRankLine: { fontSize: 13, color: colors.textSecondary },
  analyticsMetricsRow: {
    flexDirection: 'row',
    flexWrap: 'nowrap',
    gap: spacing.sm,
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  // Forces exactly three tiles into one compact row (concept mockup) instead
  // of MetricCard's default `minWidth: '46%'`, which is tuned for a 2-up
  // grid and would wrap a 3rd tile onto its own oversized row here.
  analyticsMetricTile: { flexBasis: 0, flexGrow: 1, minWidth: 0, paddingHorizontal: spacing.sm },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  sectionHeaderLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionTotal: { fontSize: 11, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  headerLink: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  // One grouped surface per lineup section (Starters, Bench) with a
  // PlayerIdentityRow per player and hairline dividers between them,
  // instead of a separately bordered/backgrounded card per player — see
  // Magna Carta §12 (card philosophy) and MatchupScreen's StarterSection,
  // which established this exact grouped-card pattern first.
  groupCard: { padding: spacing.md, paddingVertical: spacing.xs },
  compactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    gap: spacing.sm,
  },
  compactDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  compactIdentity: { flex: 1 },
  valueColumn: { alignItems: 'flex-end', marginLeft: spacing.sm, gap: 2 },
  valueNumber: { fontSize: 19, fontWeight: '800', color: colors.accent },
  valueNumberMuted: { color: colors.textSecondary },
  valueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  linkRowText: { fontSize: 13, fontWeight: '700', color: colors.accent },
  notice: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
