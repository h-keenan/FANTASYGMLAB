import React, { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AnimatedCard from '../components/AnimatedCard';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import CircularProgressRing from '../components/CircularProgressRing';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import InsightRow from '../components/InsightRow';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import SkeletonBlock from '../components/SkeletonBlock';
import SharedTradeIdeaCard from '../components/TradeIdeaCard';
import { TradeAssetRow } from './DashboardScreen';
import {
  api,
  TEAM_STANCE_OPTIONS,
  type GmPlanFocusArea,
  type GmPlanResponse,
  type GmPlanTradeItem,
  type GmTarget,
  type TradeIdea,
  type LineupPlayer,
  type PlayoffOddsTeam,
  type RankedPlayer,
  type TeamRanking,
} from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { buildPlanSnapshot, deadlineWeek, type PlanSnapshotTile } from '../lib/gmPlanSnapshot';
import { useGmStance } from '../context/GmStanceContext';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GmPlan'>;
type IconName = React.ComponentProps<typeof Ionicons>['name'];
type Tab = 'overview' | 'trades' | 'core' | 'watching';

const TABS: Array<{ key: Tab; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'trades', label: 'Trades' },
  { key: 'core', label: 'Core' },
  { key: 'watching', label: 'Watching' },
];

const FOCUS_META: Record<string, { icon: IconName }> = {
  standing: { icon: 'stats-chart-outline' },
  trade_opportunities: { icon: 'swap-horizontal-outline' },
  roster_construction: { icon: 'layers-outline' },
};

const TILE_ICON: Record<PlanSnapshotTile['key'], IconName> = {
  power: 'stats-chart-outline',
  capital: 'layers-outline',
  odds: 'trophy-outline',
  record: 'document-text-outline',
  starter: 'people-outline',
  bench: 'albums-outline',
  age: 'person-outline',
};

/**
 * GM Plan — the owner's concept structure: Overview | Trades | Core |
 * Watching. Overview is Team Situation (the declared stance, through the
 * shared GmStanceContext, plus the real trade-deadline banner), the Plan
 * Snapshot tiles and the top trade ideas; Trades adds the rest of the
 * season-arc roadmap; Core is the protected (untouchable) players; Watching
 * is the GM Targets list. Everything traces to a real signal; a tile or
 * section with no data is omitted or says so honestly. Mirrors web-next's
 * GmPlanContent.
 */
export default function GmPlanScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const { stance, setStance } = useGmStance(leagueId);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<GmPlanResponse | null>(null);
  const [tab, setTab] = useState<Tab>('overview');
  const [showRoster, setShowRoster] = useState(false);
  const [snapshot, setSnapshot] = useState<PlanSnapshotTile[]>([]);
  const [roster, setRoster] = useState<LineupPlayer[]>([]);
  const [targets, setTargets] = useState<GmTarget[]>([]);
  const [ranked, setRanked] = useState<Map<string, RankedPlayer>>(new Map());
  const [busyPlayerId, setBusyPlayerId] = useState<string | null>(null);
  const [tradeWindow, setTradeWindow] = useState<GmPlanResponse['trade_window']>(undefined);

  useScreenHeaderTitle(navigation, 'GM Plan', leagueName);

  const load = useCallback(
    async (isRefresh: boolean) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      try {
        const [planResult, myTeam, targetsResult, rankings] = await Promise.all([
          api.getGmPlan(leagueId, { lens: 'Dynasty' }),
          api.getLeagueMyTeam(leagueId),
          api.getGmTargets(leagueId),
          api.getLeagueRankings(leagueId),
        ]);
        setPlan(planResult);
        setTradeWindow(planResult.trade_window ?? myTeam.trade_window);
        const seen = new Set<string>();
        setRoster(
          [...myTeam.starters, ...myTeam.bench].filter((p) => (seen.has(p.player_id) ? false : (seen.add(p.player_id), true))),
        );
        setTargets(targetsResult.targets);
        setRanked(new Map(rankings.players.map((p) => [p.player_id, p])));

        // Best-effort snapshot sources: a tile just doesn't render if a call fails.
        const [teamsResult, oddsResult] = await Promise.all([
          api.getLeagueTeamRankings(leagueId).catch(() => null),
          api.getLeaguePlayoffOdds(leagueId).catch(() => null),
        ]);
        const teams: TeamRanking[] = teamsResult?.teams ?? [];
        const rosterId = myTeam.roster_id;
        const odds: PlayoffOddsTeam | null = oddsResult?.teams?.find((t) => t.roster_id === rosterId) ?? null;
        setSnapshot(buildPlanSnapshot(teams.find((t) => t.roster_id === rosterId) ?? null, teams.length, odds));
      } catch (err) {
        setError(toUserErrorMessage(err, 'Failed to load GM Plan.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [leagueId],
  );

  useFocusEffect(
    useCallback(() => {
      void load(false);
    }, [load]),
  );

  const protectedIds = useMemo(() => new Set(targets.filter((t) => t.untouchable).map((t) => t.player_id)), [targets]);
  const protectedRows = useMemo(() => roster.filter((p) => protectedIds.has(p.player_id)), [roster, protectedIds]);
  const otherRows = useMemo(() => roster.filter((p) => !protectedIds.has(p.player_id)), [roster, protectedIds]);
  const watching = useMemo(() => targets.filter((t) => !t.untouchable), [targets]);

  const onToggleProtect = useCallback(
    async (playerId: string, next: boolean) => {
      setBusyPlayerId(playerId);
      const previous = targets;
      const tracked = targets.some((t) => t.player_id === playerId);
      setTargets((prev) =>
        tracked
          ? prev.map((t) => (t.player_id === playerId ? { ...t, untouchable: next } : t))
          : [...prev, { player_id: playerId, source_surface: 'team_stance', created_at: null, untouchable: next }],
      );
      try {
        if (next && !tracked) {
          const added = await api.addGmTarget(leagueId, playerId, 'team_stance');
          if (!added.ok) throw new Error(added.reason || 'not_available');
        }
        if (next || tracked) {
          const result = await api.setGmTargetUntouchable(leagueId, playerId, next);
          if (!result.ok) throw new Error(result.reason || 'not_available');
        }
      } catch {
        setTargets(previous);
      } finally {
        setBusyPlayerId(null);
      }
    },
    [leagueId, targets],
  );

  const onRemoveTarget = useCallback(
    (playerId: string) => {
      const previous = targets;
      setTargets((prev) => prev.filter((t) => t.player_id !== playerId));
      api.removeGmTarget(leagueId, playerId).catch(() => setTargets(previous));
    },
    [leagueId, targets],
  );

  if (loading) {
    return (
      <View style={[styles.container, { paddingTop: headerHeight }]}>
        <GridBackground />
        <View style={styles.scrollContent}>
          <SkeletonBlock height={44} style={styles.skeleton} />
          <SkeletonBlock height={170} style={styles.skeleton} />
          <SkeletonBlock height={230} style={styles.skeleton} />
          <SkeletonBlock height={300} style={styles.skeleton} />
        </View>
      </View>
    );
  }

  if (error && !plan) {
    return (
      <View style={[styles.container, { paddingTop: headerHeight }]}>
        <GridBackground />
        <ErrorState
          title="Couldn't load GM Plan"
          message={error}
          onRetry={() => {
            setLoading(true);
            void load(false);
          }}
        />
      </View>
    );
  }

  const gated = !plan || plan.quiet || plan.focus_areas.length === 0;
  const locked = plan?.is_premium === false;
  const weekAhead = deadlineWeek(tradeWindow);
  const pastDeadline = Boolean(tradeWindow?.trade_deadline_passed);
  const tradeArea = plan?.focus_areas.find((a) => a.key === 'trade_opportunities');
  const tradeItems = (tradeArea?.items ?? []).filter((i): i is GmPlanTradeItem => 'partner_team_name' in i);
  const otherAreas = (plan?.focus_areas ?? []).filter((a) => a.key !== 'trade_opportunities');
  const openTradeHub = () => navigation.navigate('Trades', { leagueId, leagueName, initialTab: 'block' });

  const gateNotice = locked ? (
    <PremiumLock
      title={plan?.upsell?.title || 'Your season-arc roadmap'}
      description={plan?.upsell?.body || 'GM Plan is a Premium feature: where you stand, your best trade paths, and your roster construction.'}
    />
  ) : gated ? (
    <AnimatedCard style={styles.hero}>
      <AppText style={styles.quietText}>
        {plan?.reason === 'no_sleeper_username_linked'
          ? 'Link your Sleeper account to see a GM Plan for this league.'
          : 'Not enough to build a GM Plan yet.'}
      </AppText>
    </AnimatedCard>
  ) : null;

  const tradeCards = (limit?: number) =>
    gateNotice ??
    (tradeItems.length === 0 ? (
      <EmptyState
        icon="swap-horizontal-outline"
        title="No trade ideas right now"
        subtitle={tradeArea?.watch_for || 'Check back as rosters change.'}
        actionLabel="Open Trade Hub"
        onPressAction={openTradeHub}
      />
    ) : (
      <View style={styles.stack}>
        {(limit ? tradeItems.slice(0, limit) : tradeItems).map((item, index) => (
          item.send_assets?.length || item.receive_assets?.length ? (
            // Same idea card as the Trade Hub screen (GM Plan only carries a
            // subset of the idea fields, so the card hides what is absent).
            <SharedTradeIdeaCard
              key={`trade-${index}`}
              idea={gmPlanItemToIdea(item)}
              leagueId={leagueId}
              leagueName={leagueName}
              navigation={navigation}
            />
          ) : (
            <TradeIdeaCard key={`trade-${index}`} item={item} onViewDetails={openTradeHub} />
          )
        ))}
      </View>
    ));

  const protectRow = (player: LineupPlayer, isLast: boolean) => (
    <View key={player.player_id} style={[styles.row, !isLast && styles.rowDivider]}>
      <View style={styles.identity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          showDivider={false}
        />
      </View>
      <OverallRatingBadge rating={ranked.get(player.player_id)?.overall_rating ?? null} />
      <TouchableOpacity
        style={[styles.tag, protectedIds.has(player.player_id) && styles.tagActive]}
        onPress={() => onToggleProtect(player.player_id, !protectedIds.has(player.player_id))}
        disabled={busyPlayerId === player.player_id}
        accessibilityLabel={protectedIds.has(player.player_id) ? 'Remove protected flag' : 'Mark protected'}
      >
        {busyPlayerId === player.player_id ? (
          <ActivityIndicator size="small" color={colors.textSecondary} />
        ) : (
          <AppText style={[styles.tagText, protectedIds.has(player.player_id) && styles.tagTextActive]}>
            {protectedIds.has(player.player_id) ? 'Protected' : 'Protect'}
          </AppText>
        )}
      </TouchableOpacity>
    </View>
  );

  const rosterLine = (
    <TouchableOpacity
      style={styles.moreRow}
      onPress={() => {
        setTab('core');
        setShowRoster(true);
      }}
    >
      <AppText style={styles.moreText}>
        {otherRows.length} more player{otherRows.length === 1 ? '' : 's'} on your roster
      </AppText>
      <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
    </TouchableOpacity>
  );

  const link = (label: string, onPress: () => void) => (
    <TouchableOpacity onPress={onPress} hitSlop={8}>
      <AppText style={styles.link}>{label}</AppText>
    </TouchableOpacity>
  );

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />

      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
      >
        {error ? <AppText style={styles.error}>{error}</AppText> : null}
        <View style={styles.tabs}>
          <SegmentedTabBar options={TABS} active={tab} onChange={setTab} />
        </View>

        {tab === 'overview' ? (
          <>
            <SectionHeading title="Team Situation" icon="compass-outline" />
            <AnimatedCard style={styles.situation}>
              <View style={styles.stanceRow}>
                {TEAM_STANCE_OPTIONS.map((option) => {
                  const active = stance === option.value;
                  return (
                    <TouchableOpacity
                      key={option.value}
                      style={[styles.stanceChip, active && styles.stanceChipActive]}
                      onPress={() => {
                        if (!active) setStance(option.value);
                      }}
                      accessibilityState={{ selected: active }}
                    >
                      <AppText style={[styles.stanceLabel, active && styles.stanceLabelActive]}>{option.label}</AppText>
                    </TouchableOpacity>
                  );
                })}
              </View>
              {TEAM_STANCE_OPTIONS.find((o) => o.value === stance) ? (
                <AppText style={styles.caption}>{TEAM_STANCE_OPTIONS.find((o) => o.value === stance)!.description}</AppText>
              ) : null}
              {weekAhead !== null ? (
                <TouchableOpacity style={styles.banner} onPress={openTradeHub}>
                  <Ionicons name="megaphone-outline" size={18} color={colors.accent} />
                  <View style={styles.bannerText}>
                    <AppText style={styles.bannerTitle}>Trade deadline: Week {weekAhead}</AppText>
                    <AppText style={styles.caption}>Declaring a stance sharpens your recommendations.</AppText>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
              ) : pastDeadline ? (
                <AppText style={styles.caption}>Past the trade deadline</AppText>
              ) : null}
            </AnimatedCard>

            {snapshot.length > 0 ? (
              <>
                <SectionHeading
                  title="Plan Snapshot"
                  icon="speedometer-outline"
                  right={link('Full analysis', () => navigation.navigate('MyTeam', { leagueId, leagueName }))}
                />
                <View style={styles.grid}>
                  {snapshot.map((tile) => (
                    <SnapshotCell key={tile.key} tile={tile} styles={styles} colors={colors} />
                  ))}
                </View>
              </>
            ) : null}

            {!gateNotice && (plan?.season_phase_label || plan?.headline) ? (
              <AnimatedCard style={styles.hero} glow>
                {plan?.season_phase_label ? (
                  <AppText style={styles.phaseLabel}>{plan.season_phase_label.toUpperCase()}</AppText>
                ) : null}
                {plan?.headline ? <AppText style={styles.headline}>{plan.headline}</AppText> : null}
              </AnimatedCard>
            ) : null}

            <SectionHeading title="Trade Opportunities" icon="swap-horizontal-outline" right={link('View all', openTradeHub)} />
            {tradeCards(2)}

            {roster.length > 0 ? (
              <>
                <SectionHeading title="Protected Core" icon="lock-closed-outline" right={link('View all', () => setTab('core'))} />
                {protectedRows.length > 0 ? (
                  <AnimatedCard style={styles.listCard}>
                    {protectedRows.slice(0, 3).map((p, i, arr) => protectRow(p, i === arr.length - 1))}
                  </AnimatedCard>
                ) : null}
                {otherRows.length > 0 ? rosterLine : null}
              </>
            ) : null}
          </>
        ) : null}

        {tab === 'trades' ? (
          <>
            <SectionHeading title="Trade Opportunities" icon="swap-horizontal-outline" right={link('View all', openTradeHub)} />
            {tradeCards()}
            {!gateNotice ? otherAreas.map((area) => <FocusAreaSection key={area.key} focusArea={area} />) : null}
          </>
        ) : null}

        {tab === 'core' ? (
          <>
            <SectionHeading
              title="Protected Core"
              icon="lock-closed-outline"
              caption="Players you won't trade. Same flag as Watching's untouchable."
            />
            {roster.length === 0 ? (
              <EmptyState icon="people-outline" title="No roster players found for this league" />
            ) : (
              <>
                {protectedRows.length > 0 ? (
                  <AnimatedCard style={styles.listCard}>
                    {protectedRows.map((p, i) => protectRow(p, i === protectedRows.length - 1))}
                  </AnimatedCard>
                ) : (
                  <EmptyState
                    icon="lock-open-outline"
                    title="No protected players yet"
                    subtitle="Protect the players you won't trade."
                    actionLabel={showRoster ? undefined : 'Show roster'}
                    onPressAction={() => setShowRoster(true)}
                  />
                )}
                {otherRows.length > 0 ? (
                  showRoster ? (
                    <>
                      <SectionHeading title="Rest of Roster" icon="people-outline" topGap={spacing.md} />
                      <AnimatedCard style={styles.listCard}>
                        {otherRows.map((p, i) => protectRow(p, i === otherRows.length - 1))}
                      </AnimatedCard>
                    </>
                  ) : (
                    rosterLine
                  )
                ) : null}
              </>
            )}
          </>
        ) : null}

        {tab === 'watching' ? (
          <>
            <SectionHeading title="Watching" icon="eye-outline" caption="Considering or monitoring; not trade-protected." />
            {watching.length === 0 ? (
              <EmptyState
                icon="eye-outline"
                title="Nothing here yet"
                subtitle="Add players you're considering from a player's profile."
                actionLabel="Browse players"
                onPressAction={() => navigation.navigate('Players', { leagueId, leagueName })}
              />
            ) : (
              <View style={styles.stack}>
                {watching.map((target) => {
                  const player = ranked.get(target.player_id) ?? null;
                  return (
                    <AnimatedCard key={target.player_id} style={styles.watchCard}>
                      <PlayerIdentityRow
                        playerId={target.player_id}
                        name={player?.name ?? `Player ${target.player_id}`}
                        position={player?.position}
                        team={player?.team}
                        tier={player?.tier}
                        showDivider={false}
                        onPress={player ? () => navigation.navigate('PlayerDetail', { player, leagueId, leagueName }) : undefined}
                      />
                      <View style={styles.watchMeta}>
                        {player?.score != null ? (
                          <View>
                            <AppText style={styles.valueLabel}>Value</AppText>
                            <AppText style={styles.valueText}>{Math.round(player.score).toLocaleString()}</AppText>
                          </View>
                        ) : null}
                        <OverallRatingBadge rating={player?.overall_rating} positionRank={player?.position_rank} />
                      </View>
                      <View style={styles.actions}>
                        <TouchableOpacity
                          style={styles.action}
                          disabled={!player}
                          onPress={() => player && navigation.navigate('PlayerCompare', { player, leagueId, leagueName })}
                        >
                          <AppText style={styles.actionText}>Compare</AppText>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.action} onPress={() => onToggleProtect(target.player_id, true)}>
                          <AppText style={styles.actionText}>Mark untouchable</AppText>
                        </TouchableOpacity>
                        <TouchableOpacity style={[styles.action, styles.actionDanger]} onPress={() => onRemoveTarget(target.player_id)}>
                          <AppText style={[styles.actionText, { color: colors.danger }]}>Remove</AppText>
                        </TouchableOpacity>
                      </View>
                    </AnimatedCard>
                  );
                })}
              </View>
            )}
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}

function SnapshotCell({
  tile,
  styles,
  colors,
}: {
  tile: PlanSnapshotTile;
  styles: ReturnType<typeof createStyles>;
  colors: ThemeColors;
}) {
  const percent = tile.fill === null ? null : Math.round(tile.fill * 100);
  return (
    <View style={styles.cell}>
      <View style={styles.cellBody}>
        <View style={styles.cellLabelRow}>
          <Ionicons name={TILE_ICON[tile.key]} size={13} color={colors.textTertiary} />
          <AppText style={styles.cellLabel} numberOfLines={1}>
            {tile.label}
          </AppText>
        </View>
        <AppText style={styles.cellValue}>{tile.value}</AppText>
        {tile.note ? <AppText style={styles.cellNote}>{tile.note}</AppText> : null}
        {tile.key !== 'odds' && percent !== null ? (
          <View style={styles.bar}>
            <View style={[styles.barFill, { width: `${percent}%` }]} />
          </View>
        ) : null}
      </View>
      {tile.key === 'odds' && percent !== null ? <CircularProgressRing percent={percent} size={44} strokeWidth={5} /> : null}
    </View>
  );
}

/** GM Plan trade items are a trimmed Trade Hub idea; map them onto the full
 * TradeIdea shape the shared card renders (absent fields stay empty and the
 * card hides them). */
function gmPlanItemToIdea(item: GmPlanTradeItem): TradeIdea {
  const gain = item.trade_gain ?? 0;
  return {
    partner_team_name: item.partner_team_name || 'Trade idea',
    partner_team_avatar_url: null,
    partner_team_archetype_label: '',
    partner_trade_tendency: 'Neutral',
    rationale: item.rationale,
    trade_gain: gain,
    confidence_label: item.trade_confidence_label,
    market_realism_label: '',
    reasoning_tags: [],
    package: { send: item.send_assets ?? [], receive: item.receive_assets ?? [] } as TradeIdea['package'],
    category: '',
    value_edge_band: '',
    impact_tag: '',
    landed_gm_target_player_ids: [],
  };
}

function TradeIdeaCard({ item, onViewDetails }: { item: GmPlanTradeItem; onViewDetails: () => void }) {
  const { colors } = useThemeMode();
  const { showExplanations } = useDensity();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = item.their_player_injury_display || '';
  const gain = item.trade_gain;
  const send = item.send_assets ?? [];
  const receive = item.receive_assets ?? [];
  return (
    <AccentCard accent={injury ? colors.danger : colors.accent}>
      <View style={styles.tradeHeader}>
        <AppText style={styles.tradeTitle} numberOfLines={1}>
          {item.partner_team_name || 'Trade idea'}
        </AppText>
        {gain != null ? (
          <AppText style={[styles.gain, { color: gain > 0 ? colors.success : gain < 0 ? colors.danger : colors.textSecondary }]}>
            {gain > 0 ? '+' : ''}
            {Math.round(gain).toLocaleString()}
          </AppText>
        ) : null}
      </View>
      {send.length > 0 || receive.length > 0 ? (
        <View style={styles.stack}>
          <AppText style={styles.sideLabel}>YOU SEND</AppText>
          {send.map((asset, i) => (
            <TradeAssetRow key={`s${i}`} asset={asset} />
          ))}
          <AppText style={styles.sideLabel}>YOU GET</AppText>
          {receive.map((asset, i) => (
            <TradeAssetRow key={`r${i}`} asset={asset} />
          ))}
        </View>
      ) : (
        <AppText style={styles.caption}>
          {item.my_player} → {injury ? `${item.their_player} (${injury})` : item.their_player}
        </AppText>
      )}
      <View style={styles.tradeFooter}>
        <AppText style={[styles.caption, styles.flex]}>
          {showExplanations ? item.rationale || item.trade_confidence_label : item.trade_confidence_label}
        </AppText>
        <TouchableOpacity style={styles.action} onPress={onViewDetails}>
          <AppText style={styles.actionText}>View details</AppText>
        </TouchableOpacity>
      </View>
    </AccentCard>
  );
}

function FocusAreaSection({ focusArea }: { focusArea: GmPlanFocusArea }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const icon = FOCUS_META[focusArea.key]?.icon ?? 'ellipse-outline';

  return (
    <View style={styles.section}>
      <SectionHeading title={focusArea.title} icon={icon} />
      {focusArea.framing ? <AppText style={styles.caption}>{focusArea.framing}</AppText> : null}

      {focusArea.status === 'no_signal' ? (
        <AnimatedCard style={styles.listCard}>
          <InsightRow
            icon="information-circle-outline"
            color={colors.textSecondary}
            headline="Nothing to flag right now"
            detail={focusArea.watch_for}
            last
          />
        </AnimatedCard>
      ) : (
        <AnimatedCard style={styles.listCard}>
          {focusArea.items.map((item, index) => {
            const last = index === focusArea.items.length - 1;
            if ('injury_need_positions' in item) {
              const positions = item.injury_need_positions.join(', ');
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon="alert-circle-outline"
                  color={colors.danger}
                  headline={`${item.health_flag || item.label}: ${positions}`}
                  detail={item.summary || `No healthy bench cover at ${positions}.`}
                  last={last}
                />
              );
            }
            if ('rank' in item) {
              const tieNote = item.tied ? ' (tied)' : '';
              const weakSpot = 'relative_weak_spot' in item && item.relative_weak_spot;
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon={weakSpot ? 'alert-circle-outline' : 'checkmark-circle-outline'}
                  color={weakSpot ? colors.danger : colors.accent}
                  headline={`${item.label}: ${item.rank}${item.total_teams ? ` of ${item.total_teams}` : ''}${tieNote}`}
                  detail={weakSpot ? 'Relative weak spot in this league.' : undefined}
                  last={last}
                />
              );
            }
            if ('wins' in item) {
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon="ribbon-outline"
                  color={colors.accent}
                  headline={`Record: ${item.wins ?? 0}-${item.losses ?? 0}${item.ties ? `-${item.ties}` : ''}`}
                  last={last}
                />
              );
            }
            if ('playoff_probability' in item) {
              const statusNote = item.clinched ? ' · Clinched' : item.eliminated ? ' · Eliminated' : '';
              const seedNote = item.median_seed ? `, projected ${item.median_seed}-seed` : '';
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon="trophy-outline"
                  color={colors.accent}
                  headline={`${Math.round(item.playoff_probability)}% to make the playoffs${seedNote}${statusNote}`}
                  last={last}
                />
              );
            }
            return null;
          })}
        </AnimatedCard>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    scrollContent: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },
    skeleton: { marginBottom: spacing.md },
    error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
    tabs: { marginBottom: spacing.md },
    stack: { gap: spacing.sm },
    flex: { flex: 1 },
    hero: { marginBottom: spacing.lg, gap: spacing.xs },
    quietText: { fontSize: 14, color: colors.textSecondary, lineHeight: 20 },
    phaseLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.6, color: colors.premium },
    headline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, lineHeight: 22 },
    caption: { fontSize: 12, color: colors.textSecondary },
    link: { fontSize: 12, fontWeight: '700', color: colors.accent },
    situation: { gap: spacing.sm, marginBottom: spacing.lg },
    stanceRow: { flexDirection: 'row', gap: spacing.sm },
    stanceChip: {
      flex: 1,
      alignItems: 'center',
      paddingVertical: spacing.sm,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      backgroundColor: colors.surface,
    },
    stanceChipActive: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
    stanceLabel: { fontSize: 12, fontWeight: '700', color: colors.textPrimary, textTransform: 'uppercase', letterSpacing: 0.4 },
    stanceLabelActive: { color: colors.accentOnTint },
    banner: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      padding: spacing.sm,
      borderRadius: radii.md,
      backgroundColor: colors.accentMuted,
    },
    bannerText: { flex: 1, gap: 2 },
    bannerTitle: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.lg },
    cell: {
      width: '48.5%',
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      backgroundColor: colors.surface,
    },
    cellBody: { flex: 1, gap: 4 },
    cellLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    cellLabel: { flexShrink: 1, fontSize: 11.5, color: colors.textTertiary },
    cellValue: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    cellNote: { fontSize: 11.5, color: colors.textTertiary },
    bar: { height: 5, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' },
    barFill: { height: 5, backgroundColor: colors.accent },
    tradeHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.sm },
    tradeTitle: { flex: 1, fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    gain: { fontSize: 15, fontWeight: '800' },
    sideLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, color: colors.textTertiary },
    tradeFooter: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm },
    action: {
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderRadius: radii.sm,
      borderWidth: 1,
      borderColor: colors.accent,
      alignItems: 'center',
    },
    actionText: { fontSize: 12, fontWeight: '700', color: colors.accent },
    actionDanger: { borderColor: colors.danger },
    section: { marginBottom: spacing.lg },
    listCard: { paddingVertical: spacing.xs, marginBottom: spacing.sm },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    identity: { flex: 1 },
    tag: {
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.xs,
      borderRadius: radii.sm,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      minWidth: 78,
      alignItems: 'center',
    },
    tagActive: { backgroundColor: colors.premium, borderColor: colors.premium },
    tagText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
    tagTextActive: { color: colors.background },
    moreRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      backgroundColor: colors.surface,
      marginBottom: spacing.lg,
    },
    moreText: { fontSize: 13, color: colors.textSecondary },
    watchCard: { gap: spacing.sm },
    watchMeta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    valueLabel: { fontSize: 10, color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.4 },
    valueText: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    actions: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap' },
  });
}
