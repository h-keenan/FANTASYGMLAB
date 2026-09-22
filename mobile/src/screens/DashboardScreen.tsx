import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View, type ViewStyle } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import {
  api,
  type DashboardEntitlementInfo,
  type DashboardItem,
  type DashboardItemCategory,
  type InjuryImpactPlayer,
  type MatchupResponse,
  type PresentationAsset,
  type TeamRanking,
  type TeamSnapshot,
} from '../lib/api';
import PremiumLock from '../components/PremiumLock';
import ScreenHero from '../components/ScreenHero';
import BrandHeaderBar from '../components/BrandHeaderBar';
import TeamAvatar from '../components/TeamAvatar';
import TrajectoryArcs from '../components/TrajectoryArcs';
import { useOrbClearance } from '../lib/orbLayout';
import { getCachedDashboard, setCachedDashboard } from '../lib/dashboardCache';
import { diffAndRecordSeen } from '../lib/sinceLastCheckIn';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Dashboard'>;
type DashboardNavigation = Props['navigation'];

function categoryMeta(
  colors: ThemeColors,
): Record<DashboardItemCategory, { label: string; icon: React.ComponentProps<typeof Ionicons>['name']; color: string }> {
  return {
    top_priority: { label: 'Top Priority', icon: 'flash', color: colors.accent },
    watch: { label: 'Watch', icon: 'eye-outline', color: colors.danger },
    waiver_opportunity: { label: 'Waiver Opportunity', icon: 'swap-horizontal-outline', color: colors.premium },
    league_movement: { label: 'League Movement', icon: 'trending-up-outline', color: colors.textSecondary },
  };
}

// Only destinations mobile can navigate to with just {leagueId, leagueName} —
// "my_team" would need TeamRoster's ownerName/playerIds params, which this
// screen doesn't have on hand, so it's left without a button rather than
// navigating somewhere wrong.
const DESTINATION_BUTTON_LABEL: Record<string, string> = {
  trade_hub: 'Review in Trade Hub',
  waivers: 'Open Waivers',
};
const DESTINATION_ROUTE: Record<string, string> = {
  trade_hub: 'TradeHub',
  waivers: 'Waivers',
};

const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };

interface LeaguePulseTile {
  label: string;
  value: string;
  note: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
  color: string;
}

function bestByRank(teams: TeamRanking[], rankKey: 'power_rank' | 'draft_capital_rank'): TeamRanking | null {
  let best: TeamRanking | null = null;
  for (const team of teams) {
    const rank = team[rankKey];
    if (rank == null) continue;
    if (best == null || (best[rankKey] ?? Infinity) > rank) best = team;
  }
  return best;
}

/**
 * A lighter-weight adaptation of the web app's League Pulse
 * (app.py's build_home_league_pulse_items) using only what mobile's
 * /team-rankings endpoint already computes — not a byte-for-byte port.
 * "Most Active Manager" is deliberately omitted: it needs a full-season
 * Sleeper transaction scan that doesn't exist anywhere in modules/ yet
 * (web's own version depends on app.py-only intelligence-frame logic that
 * was never ported to modules/ either), so it would take real new backend
 * work rather than reusing existing data.
 */
function buildLeaguePulseTiles(teams: TeamRanking[], colors: ThemeColors): LeaguePulseTile[] {
  const contenders = teams.filter((t) => t.strategy === 'contender');
  const rebuilders = teams.filter((t) => t.strategy === 'rebuild' || t.strategy === 'tank');
  const contender = bestByRank(contenders, 'power_rank');
  const rebuilder = bestByRank(rebuilders, 'draft_capital_rank');
  const draftLeader = bestByRank(teams, 'draft_capital_rank');

  const tiles: LeaguePulseTile[] = [
    {
      label: 'Biggest Contender',
      value: contender?.team_name ?? 'No clear leader',
      note: contender ? `Power #${contender.power_rank}` : 'No contender read available yet.',
      icon: 'flame',
      color: colors.accent,
    },
    {
      label: 'Biggest Rebuilder',
      value: rebuilder?.team_name ?? 'No clear leader',
      note: rebuilder
        ? `Draft Capital #${rebuilder.draft_capital_rank} · ${rebuilder.strategy_label ?? 'Rebuild'}`
        : 'No rebuild read available yet.',
      icon: 'construct',
      color: colors.premium,
    },
    {
      label: 'Draft Capital Leader',
      value: draftLeader?.team_name ?? 'No clear leader',
      note: draftLeader ? `Draft Capital #${draftLeader.draft_capital_rank}` : 'No draft-capital read available yet.',
      icon: 'layers',
      color: colors.success,
    },
  ];
  return tiles;
}

export default function DashboardScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<DashboardItem[] | null>(null);
  const [teamSnapshot, setTeamSnapshot] = useState<TeamSnapshot | null>(null);
  const [quiet, setQuiet] = useState(false);
  const [quietReason, setQuietReason] = useState('');
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newRecommendationIds, setNewRecommendationIds] = useState<Set<string>>(new Set());
  const [isFirstVisit, setIsFirstVisit] = useState(true);
  const [teamRankings, setTeamRankings] = useState<TeamRanking[] | null>(null);
  const [matchup, setMatchup] = useState<MatchupResponse | null>(null);
  const [entitlement, setEntitlement] = useState<DashboardEntitlementInfo | null>(null);
  const { showExplanations } = useDensity();

  useScreenHeaderTitle(navigation, 'Next Move', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
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
        // Perceived-performance floor: paint the last-known-good briefing
        // immediately (if one exists) instead of a blank spinner while the
        // live request — real per-request computation server-side — is
        // still in flight. The fetch below always still runs and replaces
        // this the moment it resolves; this never substitutes for it.
        const cached = await getCachedDashboard(leagueId);
        if (!cancelled && cached && !cached.reason) {
          setItems(cached.items);
          setTeamSnapshot(cached.team_snapshot);
          setEntitlement(cached.entitlement ?? null);
          setQuiet(cached.quiet);
          setQuietReason(cached.quiet_reason ?? '');
          setLoading(false);
        }
        try {
          const result = await api.getLeagueDashboard(leagueId);
          if (cancelled) return;
          if (result.reason) {
            setNotReadyReason(result.reason);
          } else {
            setItems(result.items);
            setTeamSnapshot(result.team_snapshot);
            setEntitlement(result.entitlement ?? null);
            setQuiet(result.quiet);
            setQuietReason(result.quiet_reason ?? '');
            void setCachedDashboard(leagueId, result);
            const { newIds, isFirstVisit: firstVisit } = await diffAndRecordSeen(
              leagueId,
              result.items.map((item) => item.recommendation_id),
            );
            if (!cancelled) {
              setNewRecommendationIds(newIds);
              setIsFirstVisit(firstVisit);
            }
          }
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load your Next Move briefing.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      // Independent, best-effort — League Pulse is a bonus section, not
      // core to the briefing, so a failure here shouldn't touch loading/
      // error state for the rest of the screen.
      api
        .getLeagueTeamRankings(leagueId)
        .then((result) => {
          if (!cancelled) setTeamRankings(result.teams);
        })
        .catch(() => {});
      // Also best-effort: the matchup card is an entry point, not the
      // briefing itself. A bye week, a league without a current week, or a
      // failed call simply means no card.
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

  if (notReadyReason) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build your Next Move briefing for this league."}
        </AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenHero title="NEXT MOVE" subtitle={leagueName} />
      <AppText style={styles.disclaimer}>
        The real Next Move briefing for {leagueName} — the same roster-pressure, injury, need, and
        waiver signals the web app's Dashboard uses.
      </AppText>
      <QuickActionsGrid leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
      {!isFirstVisit && newRecommendationIds.size > 0 ? (
        <View style={styles.checkInBanner}>
          <Ionicons name="sparkles-outline" size={14} color={colors.accent} />
          <AppText style={styles.checkInText}>
            Since your last check-in: {newRecommendationIds.size} new{' '}
            {newRecommendationIds.size === 1 ? 'item' : 'items'} below
          </AppText>
        </View>
      ) : null}
      {teamSnapshot ? (
        <>
          <TeamSnapshotRow
            snapshot={teamSnapshot}
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
          />
          <TeamHealthContextCard snapshot={teamSnapshot} />
        </>
      ) : null}
      {matchup ? (
        <WeeklyMatchupCard
          matchup={matchup}
          leagueId={leagueId}
          leagueName={leagueName}
          navigation={navigation}
        />
      ) : null}
      {quiet || !items || items.length === 0 ? (
        <View style={styles.emptyCard}>
          <TrajectoryArcs width={120} height={82} />
          <AppText style={styles.emptyText}>
            {quietReason || 'Nothing urgent right now — your roster looks steady.'}
          </AppText>
        </View>
      ) : (
        items.map((item, index) => (
          <BriefingCard
            key={`${item.category}-${index}`}
            item={item}
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
            isNew={newRecommendationIds.has(item.recommendation_id)}
            showExplanations={showExplanations}
          />
        ))
      )}
      {entitlement && !entitlement.is_premium && entitlement.hidden_count > 0 ? (
        <View style={styles.lockWrap}>
          <PremiumLock
            title="More next moves"
            description={`See ${entitlement.hidden_count} more roster, trade, waiver, and health signal${entitlement.hidden_count === 1 ? '' : 's'} so you don't miss the next best move.`}
          />
        </View>
      ) : null}
      {teamRankings && teamRankings.length > 0 ? (
        entitlement && !entitlement.is_premium ? (
          <View style={styles.lockWrap}>
            <PremiumLock
              title="Full League Pulse"
              description="See contender, rebuilder, and draft-capital leaders across the whole league."
            />
          </View>
        ) : (
          <LeaguePulseSection teams={teamRankings} />
        )
      ) : null}
      </ScrollView>
    </View>
  );
}

function LeaguePulseSection({ teams }: { teams: TeamRanking[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tiles = buildLeaguePulseTiles(teams, colors);
  return (
    <View style={styles.pulseSection}>
      <AppText style={styles.pulseHeading}>League Pulse</AppText>
      <View style={styles.pulseGrid}>
        {tiles.map((tile) => (
          <View key={tile.label} style={[styles.pulseTile, { borderLeftColor: tile.color }]}>
            <View style={styles.pulseLabelRow}>
              <Ionicons name={tile.icon} size={12} color={tile.color} />
              <AppText style={[styles.pulseLabel, { color: tile.color }]}>{tile.label.toUpperCase()}</AppText>
            </View>
            <AppText style={styles.pulseValue} numberOfLines={1}>
              {tile.value}
            </AppText>
            <AppText style={styles.pulseNote} numberOfLines={1}>
              {tile.note}
            </AppText>
          </View>
        ))}
      </View>
    </View>
  );
}

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — the Next Move briefing needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
};

// Same icon/color per destination GmOrb's own menu already uses (Trade Hub
// 'shuffle-outline'/premium, Players 'people-outline'/violet, Waivers
// 'swap-horizontal-outline'/success, Draft Center 'albums-outline'/premium)
// — IconCircle's own docstring is "a list of rows scans by color before it
// scans by label," which only holds if the same destination always gets
// the same color everywhere, not a fresh one invented per screen.
function quickActions(colors: ThemeColors): Array<{
  label: string;
  route: 'TradeHub' | 'Players' | 'Waivers' | 'DraftCenter';
  icon: React.ComponentProps<typeof IconCircle>['name'];
  color: string;
}> {
  return [
    { label: 'Trade Hub', route: 'TradeHub', icon: 'shuffle-outline', color: colors.premium },
    { label: 'Rankings', route: 'Players', icon: 'people-outline', color: colors.violet },
    { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', color: colors.success },
    { label: 'Draft Picks', route: 'DraftCenter', icon: 'albums-outline', color: colors.premium },
  ];
}

/** The concept sheet's Dashboard panel leads with a 2x2 "Quick Actions"
 * shortcut grid (Trade Hub/Rankings/Waivers/Draft Picks) above the daily
 * briefing feed — this app's Dashboard had no equivalent shortcut row at
 * all, only the deeper GM Orb menu and per-tile destination buttons. */
function QuickActionsGrid({
  leagueId,
  leagueName,
  navigation,
}: {
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.quickActionsGrid}>
      {quickActions(colors).map((action) => (
        <TouchableOpacity
          key={action.route}
          style={[styles.quickActionCell, { borderColor: `${action.color}55` }]}
          onPress={() => navigation.navigate(action.route, { leagueId, leagueName })}
        >
          <IconCircle name={action.icon} color={action.color} size={36} />
          <AppText style={styles.quickActionLabel} numberOfLines={1}>
            {action.label}
          </AppText>
        </TouchableOpacity>
      ))}
    </View>
  );
}

function DestinationButton({
  item,
  leagueId,
  leagueName,
  navigation,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const label = DESTINATION_BUTTON_LABEL[item.destination];
  const routeName = DESTINATION_ROUTE[item.destination];
  if (!label || !routeName) return null;
  return (
    <TouchableOpacity
      style={styles.destButton}
      onPress={() => {
        if (!routeName) return;
        (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName });
      }}
    >
      <AppText style={styles.destButtonText}>{label.toUpperCase()}</AppText>
    </TouchableOpacity>
  );
}

function TradeAssetRow({ asset }: { asset: PresentationAsset }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (asset.asset_type === 'pick') {
    return (
      <View style={styles.assetRow}>
        <View style={styles.pickDisc}>
          <Ionicons name="ticket-outline" size={16} color={colors.premium} />
        </View>
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.label || 'Draft pick'}
        </AppText>
      </View>
    );
  }
  return (
    <View style={styles.assetRow}>
      <PlayerAvatar playerId={asset.player_id} size={32} tier={asset.tier} style={styles.assetAvatar} />
      <View style={styles.assetTextGroup}>
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.name ?? 'Unknown'}
        </AppText>
        <View style={styles.assetMetaRow}>
          <PositionBadge position={asset.position} />
          <AppText style={styles.assetMeta} numberOfLines={1}>
            {asset.team}
          </AppText>
        </View>
      </View>
    </View>
  );
}

function NewBadge() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.newBadge}>
      <AppText style={styles.newBadgeText}>NEW</AppText>
    </View>
  );
}

function TeamSnapshotRow({
  snapshot,
  leagueId,
  leagueName,
  navigation,
}: {
  snapshot: TeamSnapshot;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const record =
    snapshot.wins != null && snapshot.losses != null
      ? `${snapshot.wins}-${snapshot.losses}${snapshot.ties ? `-${snapshot.ties}` : ''}`
      : '—';
  const injuredCount = snapshot.injured_starters;
  // Power/Franchise/Injuries link out to a fuller view — Injuries opens the
  // same health context card just below rather than a separate screen,
  // since that's where the "why" already lives.
  const tiles: { label: string; value: string; tappable?: boolean; tone?: 'danger' }[] = [
    { label: 'Record', value: record },
  ];
  if (snapshot.power_rank != null) tiles.push({ label: 'Power', value: `#${snapshot.power_rank}`, tappable: true });
  if (snapshot.franchise_rank != null) {
    tiles.push({ label: 'Franchise', value: `#${snapshot.franchise_rank}`, tappable: true });
  }
  tiles.push({ label: 'Avg Age', value: snapshot.average_age != null ? snapshot.average_age.toFixed(1) : '—' });
  tiles.push({
    label: 'Injuries',
    value: injuredCount != null ? String(injuredCount) : '—',
    tone: injuredCount != null && injuredCount > 0 ? 'danger' : undefined,
  });
  return (
    <View style={styles.snapshotSection}>
      <View style={styles.snapshotHeaderRow}>
        <Ionicons name="stats-chart" size={14} color={colors.accent} />
        <AppText style={styles.snapshotHeaderText}>LEAGUE SNAPSHOT</AppText>
      </View>
      <View style={styles.snapshotRow}>
        {tiles.map((tile) =>
          tile.tappable ? (
            <TouchableOpacity
              key={tile.label}
              style={[styles.snapshotTile, styles.snapshotTileTappable]}
              onPress={() => navigation.navigate('Teams', { leagueId, leagueName })}
            >
              <AppText style={styles.snapshotValue} numberOfLines={1}>
                {tile.value}
              </AppText>
              <AppText style={styles.snapshotLabel}>{tile.label}</AppText>
            </TouchableOpacity>
          ) : (
            <View key={tile.label} style={styles.snapshotTile}>
              <AppText
                style={[styles.snapshotValue, tile.tone === 'danger' && styles.snapshotValueDanger]}
                numberOfLines={1}
              >
                {tile.value}
              </AppText>
              <AppText style={styles.snapshotLabel}>{tile.label}</AppText>
            </View>
          ),
        )}
      </View>
    </View>
  );
}

/**
 * Dashboard entry point for the weekly matchup — "who am I playing and who
 * should I start" is the most time-sensitive thing on this screen, so it
 * sits directly under the team snapshot rather than behind the orb only.
 *
 * Shows the season-value edge, NOT a points projection: the app has no
 * weekly-projection feed (see services/mobile_api_service.py's
 * SEASON_VALUE_BASIS_LABEL), so the number here is a season-long
 * value/opportunity total and the card says so on its face.
 */
function WeeklyMatchupCard({
  matchup,
  leagueId,
  leagueName,
  navigation,
}: {
  matchup: MatchupResponse;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const mine = matchup.my_team;
  const opponent = matchup.opponent;
  const comparison = matchup.comparison;
  if (!mine || !opponent || !comparison) return null;

  const edgeColor =
    comparison.edge === 'you'
      ? colors.successBright
      : comparison.edge === 'opponent'
        ? colors.danger
        : colors.textSecondary;

  return (
    <AnimatedCard
      glow
      style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.accent } as ViewStyle])}
      onPress={() => navigation.navigate('Matchup', { leagueId, leagueName })}
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name="american-football" size={15} color={colors.accent} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.accent }]}>
          {matchup.week != null ? `WEEK ${matchup.week} MATCHUP` : 'THIS WEEK’S MATCHUP'}
        </AppText>
      </View>
      <AppText style={styles.cardHeadline}>vs {opponent.team_name}</AppText>

      <View style={styles.matchupValueRow}>
        <View style={styles.matchupValueSide}>
          <TeamAvatar
            avatarId={mine.avatar_url}
            size={40}
            style={StyleSheet.flatten([styles.matchupAvatar, { borderColor: colors.accent }])}
          />
          <AppText style={styles.matchupSideLabel}>YOU</AppText>
          <AppText style={styles.matchupSideValue}>{Math.round(comparison.my_season_value).toLocaleString()}</AppText>
        </View>
        <AppText style={styles.matchupVersus}>VS</AppText>
        <View style={[styles.matchupValueSide, styles.matchupValueSideRight]}>
          <TeamAvatar
            avatarId={opponent.avatar_url}
            size={40}
            style={StyleSheet.flatten([styles.matchupAvatar, { borderColor: colors.danger }])}
          />
          <AppText style={styles.matchupSideLabel}>THEM</AppText>
          <AppText style={styles.matchupSideValue}>{Math.round(comparison.opponent_season_value).toLocaleString()}</AppText>
        </View>
      </View>

      <AppText style={[styles.matchupEdge, { color: edgeColor }]}>
        {comparison.headline}
        {comparison.edge === 'even'
          ? ''
          : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
      </AppText>
      {/* Straight from the API, never paraphrased into something stronger. */}
      <AppText style={styles.matchupBasis}>{comparison.basis_label}</AppText>

      <View style={styles.destButton}>
        <AppText style={styles.destButtonText}>SEE SUGGESTED STARTERS</AppText>
      </View>
    </AnimatedCard>
  );
}

/** One line of the "what's driving the flag" list — mirrors the engine's own
 * top_injury_impact_summary wording (name (POS, TEAM) - status, impact N,
 * freshness) that web renders, trimmed for a phone-width row. */
function injuryImpactLine(player: InjuryImpactPlayer): string {
  const where = [player.position, player.team].filter(Boolean).join(', ');
  const status = player.injury_status || player.injury_level;
  const detail = [
    status,
    player.roster_relevance,
    player.impact_contribution != null ? `impact ${player.impact_contribution}` : '',
    // Only surface freshness when it undercuts the read — "current"/"recent"
    // updates need no caveat, the same way web only notes stale/unknown ones.
    ['stale', 'aging', 'update unknown'].includes(player.freshness_label) ? player.freshness_label : '',
  ]
    .filter(Boolean)
    .join(' · ');
  const who = where ? `${player.name} (${where})` : player.name;
  return detail ? `${who} — ${detail}` : who;
}

/** The "why" behind the Health tile: which injuries, and which players are
 * actually carrying the impact. Same already-computed fields web shows as its
 * "Key injuries:" caption plus the injury impact note — rendered here in the
 * bulleted label/items style TeamRosterScreen already uses for archetype
 * strengths and risks. */
function TeamHealthContextCard({ snapshot }: { snapshot: TeamSnapshot }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const players = snapshot.top_injury_impact_players ?? [];
  const keyInjuries = snapshot.key_injuries_summary?.trim() ?? '';
  const fallbackSummary = snapshot.top_injury_impact_summary?.trim() ?? '';
  if (players.length === 0 && !keyInjuries && !fallbackSummary) return null;

  return (
    <AnimatedCard style={StyleSheet.flatten([styles.healthCard, styles.healthCardBorder])}>
      <View style={styles.healthHeaderRow}>
        <Ionicons name="pulse-outline" size={15} color={colors.danger} />
        <AppText style={styles.healthLabel} numberOfLines={1}>
          {snapshot.health_flag || 'Health context'}
        </AppText>
      </View>
      {keyInjuries ? <AppText style={styles.healthSummary}>Key injuries: {keyInjuries}</AppText> : null}
      {players.length > 0 ? (
        <View style={styles.detailListGroup}>
          <AppText style={styles.detailListLabel}>Driving the flag</AppText>
          {players.map((player, index) => (
            <AppText key={`${player.player_id || player.name}-${index}`} style={styles.detailListItem}>
              {'•'} {injuryImpactLine(player)}
            </AppText>
          ))}
        </View>
      ) : fallbackSummary ? (
        <AppText style={styles.detailListItem}>{fallbackSummary}</AppText>
      ) : null}
    </AnimatedCard>
  );
}

function TopPriorityTradeCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const presentation = item.presentation!;
  const gain = presentation.trade_gain;
  const gainColor = gain > 0 ? colors.successBright : gain < 0 ? colors.danger : colors.textSecondary;
  const confidenceLevel = CONFIDENCE_LEVELS[presentation.trade_confidence_label?.toLowerCase()] ?? 1;
  const routeName = DESTINATION_ROUTE[item.destination];

  return (
    <AnimatedCard
      glow
      style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.accent } as ViewStyle])}
      onPress={
        routeName
          ? () => (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName })
          : undefined
      }
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name="flash" size={15} color={colors.accent} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.accent }]}>TOP PRIORITY</AppText>
        {isNew ? <NewBadge /> : null}
        <View style={styles.tradeBadge}>
          <Ionicons name="swap-horizontal" size={12} color={colors.textSecondary} />
          <AppText style={styles.tradeBadgeText}>TRADE</AppText>
        </View>
      </View>
      <AppText style={styles.cardHeadline}>{presentation.partner_team_name}</AppText>

      <View style={styles.sideBlock}>
        <View style={[styles.sideBar, { backgroundColor: colors.danger }]} />
        <View style={styles.sideContent}>
          <AppText style={styles.sideLabel}>YOU GIVE</AppText>
          {presentation.trade_package.send.map((asset, index) => (
            <TradeAssetRow key={`send-${index}`} asset={asset} />
          ))}
        </View>
      </View>
      <View style={styles.sideBlock}>
        <View style={[styles.sideBar, { backgroundColor: colors.successBright }]} />
        <View style={styles.sideContent}>
          <AppText style={styles.sideLabel}>YOU GET</AppText>
          {presentation.trade_package.receive.map((asset, index) => (
            <TradeAssetRow key={`receive-${index}`} asset={asset} />
          ))}
        </View>
      </View>

      <View style={styles.valueRow}>
        <AppText style={styles.valueLabel}>
          TRADE VALUE / {presentation.trade_market_realism_label.toUpperCase()}
        </AppText>
        <AppText style={[styles.valueNumber, { color: gainColor }]}>
          {gain > 0 ? '+' : ''}
          {gain}
        </AppText>
      </View>
      <View style={styles.meterRow}>
        <AppText style={styles.meterLabel}>CONFIDENCE</AppText>
        <View style={styles.meterSegments}>
          {[1, 2, 3].map((segment) => (
            <View
              key={segment}
              style={[
                styles.meterSegment,
                { backgroundColor: segment <= confidenceLevel ? colors.accent : colors.borderStrong },
              ]}
            />
          ))}
        </View>
        <AppText style={styles.meterValue}>{presentation.trade_confidence_label}</AppText>
      </View>

      {showExplanations && item.reason ? <AppText style={styles.cardReason}>{item.reason}</AppText> : null}
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AnimatedCard>
  );
}

function BriefingCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (item.presentation?.trade_package) {
    return (
      <TopPriorityTradeCard
        item={item}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        isNew={isNew}
        showExplanations={showExplanations}
      />
    );
  }
  const meta = categoryMeta(colors)[item.category] ?? categoryMeta(colors).watch;
  return (
    <AnimatedCard style={StyleSheet.flatten([styles.card, { borderLeftColor: meta.color } as ViewStyle])}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name={meta.icon} size={15} color={meta.color} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: meta.color }]}>{meta.label.toUpperCase()}</AppText>
        {isNew ? <NewBadge /> : null}
      </View>
      <AppText style={styles.cardHeadline}>{item.headline}</AppText>
      {showExplanations && item.reason ? <AppText style={styles.cardReason}>{item.reason}</AppText> : null}
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.lg, lineHeight: 16, textAlign: 'center' },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  quickActionCell: {
    flexBasis: '22%',
    flexGrow: 1,
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xs,
    gap: spacing.xs,
    borderRadius: radii.md,
    borderWidth: 1,
    backgroundColor: colors.surface,
  },
  quickActionLabel: { fontSize: 11, fontWeight: '600', color: colors.textSecondary, textAlign: 'center' },
  lockWrap: { marginTop: spacing.md },
  pulseSection: { marginTop: spacing.lg },
  pulseHeading: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
  },
  pulseGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  pulseTile: {
    flexBasis: '48%',
    flexGrow: 1,
    backgroundColor: colors.surfaceSolid,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 3,
    padding: spacing.md,
  },
  pulseLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  pulseLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
  pulseValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginTop: 4 },
  pulseNote: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  checkInBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.accentMuted,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  checkInText: { fontSize: 12, fontWeight: '600', color: colors.accent, flexShrink: 1 },
  matchupValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.md,
  },
  matchupValueSide: { flex: 1 },
  matchupValueSideRight: { alignItems: 'flex-end' },
  matchupAvatar: { borderWidth: 2, marginBottom: spacing.xs },
  matchupSideLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
  matchupSideValue: { fontSize: 20, fontWeight: '800', color: colors.textPrimary, marginTop: 2 },
  matchupVersus: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    color: colors.textTertiary,
    paddingHorizontal: spacing.sm,
  },
  matchupEdge: { fontSize: 13, fontWeight: '700', marginTop: spacing.md },
  matchupBasis: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs },
  snapshotSection: { marginBottom: spacing.md },
  snapshotHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
  snapshotHeaderText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  snapshotRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  snapshotTile: {
    flexBasis: '30%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  snapshotTileTappable: { borderColor: colors.accentMuted },
  healthCard: { padding: spacing.lg, gap: spacing.sm, marginBottom: spacing.md },
  // Same left-border accent language BriefingCard/TopPriorityTradeCard/
  // WeeklyMatchupCard use — this card was the one surface on Dashboard still
  // rendering as a flat, unaccented block despite being the "injury/watch"
  // category everywhere else on the screen colors red.
  healthCardBorder: { borderLeftWidth: 4, borderLeftColor: colors.danger },
  healthHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  healthLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.danger,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    flexShrink: 1,
  },
  healthSummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  // Matches TeamRosterScreen's archetype strengths/risks list styling.
  detailListGroup: { gap: 2 },
  detailListLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  detailListItem: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  snapshotValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  snapshotValueDanger: { color: colors.danger },
  snapshotLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  newBadge: {
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 2,
    marginLeft: spacing.xs,
  },
  newBadgeText: { fontSize: 8, fontWeight: '800', color: colors.background, letterSpacing: 0.4 },
  card: {
    borderLeftWidth: 4,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
  cardIcon: { marginRight: spacing.xs },
  cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  cardHeadline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  cardReason: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  tradeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: 'auto',
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  tradeBadgeText: { fontSize: 9, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5 },
  sideBlock: { flexDirection: 'row', marginTop: spacing.sm },
  sideBar: { width: 3, borderRadius: 2, marginRight: spacing.sm },
  sideContent: { flex: 1, gap: spacing.xs },
  sideLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  assetAvatar: {},
  pickDisc: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.backgroundElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  assetMeta: { fontSize: 11, color: colors.textSecondary },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 1 },
  valueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  valueLabel: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  valueNumber: { fontSize: 18, fontWeight: '800' },
  meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  meterSegments: { flexDirection: 'row', gap: 3 },
  meterSegment: { width: 14, height: 4, borderRadius: 2 },
  meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  destButton: {
    marginTop: spacing.md,
    borderWidth: 1.5,
    borderColor: colors.accent,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  destButtonText: { fontSize: 12, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  emptyText: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  });
}
