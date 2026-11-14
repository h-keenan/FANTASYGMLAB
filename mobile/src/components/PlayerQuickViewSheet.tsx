import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import AwardsStrip from './AwardsStrip';
import Button from './Button';
import DecisionFitCard from './DecisionFitCard';
import MetricCard from './MetricCard';
import ModelRadarChart from './ModelRadarChart';
import PercentileExplorerSheet from './PercentileExplorerSheet';
import PlayerHero from './PlayerHero';
import PlayerLeagueActions from './PlayerLeagueActions';
import { AvailabilityBlock, LatestNewsSection } from './PlayerQuickViewNews';
import { useTabs } from './Tabs';
import { pqvBioForContext, pqvRealWorld } from '../lib/pqvContext';
import { rowsAsOf, simAsOfSeason } from '../lib/simAsOf';
import PlayerTrendsPanel from './PlayerTrendsPanel';
import SectionHeading from './SectionHeading';
import SkeletonBlock, { SkeletonChart } from './SkeletonBlock';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import PlayerValueHistory from './PlayerValueHistory';
import { ratingHistoryCaption } from '../lib/valueHistoryPresentation';
import SubRatingRow from './SubRatingRow';
import { BadgeLegendSheet, PlayerBadges } from './PlayerBadge';
import ToneBadge from './ToneBadge';
import { badgeFromInjury, badgeFromTag } from '../lib/playerBadges';
import SeasonStatsRows from './SeasonStatsRows';
import { HeadlineTiles } from './StatRows';
import UsageBlock from './UsageBlock';
import { headlineRows } from '../lib/statRows';
import ValuesCredit from './ValuesCredit';
import { useThemeMode } from '../context/ThemeModeContext';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { api } from '../lib/api';
import { injuryTone } from '../lib/injuryDisplay';
import { cleanInjuryLabel } from '../lib/playerAvailability';
import { getLastLeague } from '../lib/lastLeague';
import { isTradeAnalyzerRoute } from '../lib/tradeShortcuts';
import { type ExplorerPlayer } from '../lib/percentileExplorer';
import { overallRatingColor } from '../lib/percentile';
import { resolvePlayerTier } from '../lib/playerTier';
import {
  fullProfileTarget,
  leagueScopedIdentity,
  stubPlayer,
  type QuickViewLeague,
  type QuickViewRequest,
} from '../lib/playerQuickView';
import { rankLine, rookieBadge, tierOpportunityMismatchCaption, opportunityUsageCaption } from '../lib/playerQuickViewPresentation';
import { queryKeys } from '../lib/queryKeys';
import { isOnWaiverList } from '../lib/waiverHighlight';
import { playerSubRatings } from '../lib/subRatings';
import { navigationRef } from '../navigation/navigationRef';
import { nextSheetSnap, orderPlayerSheetTabs, type SheetSnap } from '../lib/playerAnatomy';
import { radii, scrim, sheetHeight, spacing, type ThemeColors } from '../theme';

type ExplorerTarget = { key: string; label: string };

/** One web-PQV section: hairline top rule, small caps heading. */
function tagToneColor(tone: 'success' | 'accent' | 'warning' | 'danger' | 'muted', colors: ThemeColors): string {
  switch (tone) {
    case 'success':
      return colors.success;
    case 'accent':
      return colors.accent;
    case 'warning':
      return colors.warning;
    case 'danger':
      return colors.danger;
    default:
      return colors.textSecondary;
  }
}

export function Section({ title, icon, right, children }: { title: string; icon?: React.ComponentProps<typeof SectionHeading>['icon']; right?: React.ReactNode; children: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.section}>
      <SectionHeading title={title} icon={icon} right={right} />
      {children}
    </View>
  );
}

/**
 * The one player quick view (owner, 2026-10-24): mirrors web-next's
 * PlayerQuickView, fed by the same GET /v1/players/{id}/quick-view. Opened
 * only through PlayerQuickViewContext. Works without a league (News): it then
 * shows league-independent fields only, and "Full profile" falls back to the
 * last-used league for navigation.
 */
function insideTradeAnalyzer(): boolean {
  if (!navigationRef.isReady()) return false;
  const route = navigationRef.getCurrentRoute();
  return isTradeAnalyzerRoute(route?.name, (route?.params as { initialTab?: string } | undefined)?.initialTab);
}

/** The Fantasy Sim's own tab contents inside the Player Quick View (see `simSections`). */
export interface SimPqvSections {
  overview: React.ReactNode;
  outlook?: React.ReactNode;
  scouting?: React.ReactNode;
  history?: React.ReactNode;
  /** The two hero tiles shown in place of Value and Usage (the sim never shows the model's value). */
  heroTiles?: { label: string; value: string; note: string }[];
  /** Real-NFL record cut to the as-of season (career + game log), shown first in the Stats tab. */
  stats?: React.ReactNode;
}

export default function PlayerQuickViewSheet({
  request,
  onClose,
  simOverlay,
  asOfSeason,
  simSections,
  remote = true,
}: {
  request: QuickViewRequest;
  onClose: () => void;
  /** Fantasy Sim: game-specific sections rendered right under the hero (mirrors web PlayerQuickView). Omit everywhere else. */
  simOverlay?: React.ReactNode;
  /** Fantasy Sim only: the last fully finished real season at the sim's start (lib/simAsOf.ts). Real season stats and awards are cut to it; current usage / trend / value-history never show. */
  asOfSeason?: number;
  /** Fantasy Sim, split by tab (preferred): the game's own Overview, Outlook, Scouting and History. Present = the sim's world. */
  simSections?: SimPqvSections;
  /** false for a synthetic sim player with no real data behind the id: same layout, no remote fetches. */
  remote?: boolean;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { openPlayer } = usePlayerQuickView();
  // Fantasy Sim: the overlay marks the game's own world. No real news, real injury / availability notes or real bye here.
  const sim: SimPqvSections | null = simSections ?? (simOverlay != null ? { overview: simOverlay } : null);
  const isSim = sim != null;
  const realWorld = pqvRealWorld(isSim);
  const { player } = request;
  const [explorer, setExplorer] = useState<ExplorerTarget | null>(null);
  const [legendOpen, setLegendOpen] = useState(false);
  const scoped = leagueScopedIdentity(request);

  const detailQuery = useQuery({
    queryKey: queryKeys.playerQuickView(player.player_id),
    queryFn: () => api.getPlayerQuickView(player.player_id),
    enabled: remote,
  });
  const awardsQuery = useQuery({
    queryKey: [...queryKeys.playerQuickView(player.player_id), 'awards'],
    queryFn: () => api.getPlayerAwards(player.player_id),
    staleTime: 5 * 60 * 1000,
    enabled: remote,
  });

  // Value history (daily rating snapshots) is lazy and never gates the sheet.
  const historyQuery = useQuery({
    queryKey: queryKeys.playerRatingHistory(player.player_id),
    queryFn: () => api.getPlayerRatingHistory(player.player_id),
    enabled: detailQuery.isSuccess,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  // News is lazy and independent: it starts once the quick view has loaded
  // (never competes with it) and never gates the sheet.
  const newsQuery = useQuery({
    queryKey: [...queryKeys.playerQuickView(player.player_id), 'news'],
    queryFn: () => api.getPlayerNews(player.player_id, 3, { groupDuplicates: true }),
    enabled: detailQuery.isSuccess && realWorld.fetchNews,
    staleTime: 2 * 60 * 1000,
  });
  const newsLoading = detailQuery.isSuccess && realWorld.fetchNews && newsQuery.isPending;

  // "View on Waivers" only when this player really is on the league's waiver
  // list. Same query key/fn Dashboard uses, so the cache is shared.
  const waiverLeagueId = request.league?.leagueId ?? null;
  const waiversQuery = useQuery({
    queryKey: queryKeys.waivers(waiverLeagueId ?? ''),
    queryFn: () => api.getLeagueWaivers(waiverLeagueId as string),
    enabled: !!waiverLeagueId && request.sourceLabel !== 'Waivers',
    staleTime: 2 * 60 * 1000,
  });
  const waiversData = waiversQuery.data ?? null;
  const onWaivers =
    !!request.league &&
    !!waiversData &&
    isOnWaiverList(player.player_id, {
      priorityAdds: waiversData.priority_adds ?? [],
      stashCandidates: waiversData.stash_candidates ?? [],
      watchlistCandidates: waiversData.watchlist_candidates ?? [],
      faabTargets: waiversData.faab_targets ?? [],
      players: waiversData.players ?? [],
      idpPlayers: waiversData.idp_players ?? [],
      isPremium: waiversData.entitlement?.is_premium ?? true,
    });

  const [fallback, setFallback] = useState<QuickViewLeague | null>(null);
  useEffect(() => {
    if (request.league || !remote) return;
    let cancelled = false;
    void getLastLeague().then((last) => {
      if (!cancelled && last) setFallback({ leagueId: last.leagueId, leagueName: last.leagueName });
    });
    return () => {
      cancelled = true;
    };
  }, [request.league, remote]);

  const detail = detailQuery.data ?? null;
  const resolved = detail?.identity ?? null;
  // Fantasy Sim "as-of" cut: only seasons up to the sim's start; nothing current (usage trend / profile, value history).
  const asOf = isSim ? (asOfSeason ?? simAsOfSeason(null)) : null;
  const stats = detail?.stats ? (asOf != null ? { ...detail.stats, seasons: rowsAsOf(detail.stats.seasons, asOf) } : detail.stats) : null;
  const model = detail?.model ? (asOf != null ? { ...detail.model, usage_trend: null, usage_profile: null } : detail.model) : null;
  const bio = detail?.bio ?? null;
  const allAwards = awardsQuery.data?.ok ? awardsQuery.data.awards : [];
  const awards = asOf != null ? rowsAsOf(allAwards, asOf) : allAwards;

  const name = player.name || resolved?.name || `Player ${player.player_id}`;
  const position = player.position || resolved?.position || null;
  const team = player.team || resolved?.team || null;
  const age = player.age ?? resolved?.age ?? null;
  const overallRating = player.overall_rating ?? stats?.overall_rating ?? resolved?.overall_rating ?? null;
  // The server's availability block wins; the row's raw status only drives
  // the chip (with a clean label) until it arrives.
  const availability = realWorld.showAvailability ? (resolved?.availability ?? null) : null;
  const injury = availability ? null : cleanInjuryLabel(player.injury_status);
  const target = fullProfileTarget(request, fallback);
  // League-less opens (News) borrow the last-used league for the trade
  // shortcuts too, same as Full Profile; none known means no actions.
  const actionsLeague = request.league ?? fallback;
  const loading = remote && detailQuery.isPending;
  // What a remote tab shows instead of its content while the detail loads or when it failed (null = show the content).
  const bodyGate: React.ReactNode | null = loading ? (
    <View style={styles.body}>
      <SkeletonBlock height={64} />
      <SkeletonChart />
      <SkeletonBlock height={90} />
      <SkeletonBlock height={90} />
    </View>
  ) : !remote ? null : detailQuery.isError || !detail ? (
    <AppText style={styles.muted}>Couldn&apos;t load this player&apos;s detail right now.</AppText>
  ) : null;

  const openWaivers = () => {
    if (!request.league) return;
    onClose();
    if (navigationRef.isReady()) {
      navigationRef.navigate('Waivers', {
        leagueId: request.league.leagueId,
        leagueName: request.league.leagueName,
        playerId: player.player_id,
      });
    }
  };

  const openExplorerPlayer = (other: ExplorerPlayer) => {
    setExplorer(null);
    openPlayer(
      stubPlayer({ player_id: other.player_id, name: other.name, position: other.position, team: other.team || null }),
      { leagueId: request.league?.leagueId, leagueName: request.league?.leagueName, sourceLabel: 'Percentile Explorer' },
    );
  };

  const openPlayerNews = () => {
    onClose();
    if (!navigationRef.isReady()) return;
    // With a league the full profile can open, so land on its News tab;
    // otherwise fall back to the player-filtered News screen.
    if (target) navigationRef.navigate('PlayerDetail', { ...target, initialTab: 'news' });
    else navigationRef.navigate('News', { playerId: player.player_id, playerName: name });
  };

  const openFullProfile = () => {
    if (!target) return;
    onClose();
    if (navigationRef.isReady()) navigationRef.navigate('PlayerDetail', target);
  };

  const shownBio = bio ? pqvBioForContext(bio, isSim) : null;
  const bioRows = shownBio
    ? ([
        ['Experience', shownBio.years_in_league],
        ['Draft capital', shownBio.draft_capital],
        ['College', shownBio.college],
        ['Height', shownBio.height],
        ['Weight', shownBio.weight],
        ['Bye week', shownBio.bye_week],
        ['Contract', shownBio.contract_status],
      ] as const).filter(([, v]) => Boolean(v))
    : [];

  const tierIdentity = resolvePlayerTier(scoped.tier, isDark);
  const mismatch = tierOpportunityMismatchCaption(scoped.tier, scoped.opportunityLabel);
  const usageCaption = opportunityUsageCaption(scoped.opportunityLabel, model?.usage_trend ?? null);
  const ranks = rankLine(position, scoped.overallRank, scoped.positionRank);
  const subRatings = model ? playerSubRatings(model) : [];
  const hasSubRatings = subRatings.some((item) => item.rating != null);
  const headerTags = request.tags ?? [];
  const showSignals = !!scoped.opportunityLabel || !!injury || headerTags.length > 0;

  // Peek sheet (coridian_ pick 1b): opens at half height, drag the grip up (or tap it) for full; pills never move it.
  const [snap, setSnap] = useState<SheetSnap>('peek');
  const gripStart = useRef<{ y: number; t: number } | null>(null);

  const pqvTabs = useTabs({
    id: 'pqv',
    tabs: orderPlayerSheetTabs([
    {
      key: 'overview',
      label: 'Overview',
      render: () => (
        <>
          {sim?.overview ?? null}
          {availability ? <AvailabilityBlock availability={availability} injuryItem={newsQuery.data?.injury_item ?? null} newsLoading={newsLoading} /> : null}
          {detail && remote && realWorld.showNews ? (
            <LatestNewsSection
              items={newsQuery.data ? newsQuery.data.items : null}
              loading={newsLoading}
              onSeeAll={openPlayerNews}
              hideItem={availability ? newsQuery.data?.injury_item ?? null : null}
            />
          ) : null}
          {bodyGate ?? (
            <View style={styles.body}>
              {model?.decision_fit_narrative ? <DecisionFitCard narrative={model.decision_fit_narrative} /> : null}
              <HeadlineTiles rows={headlineRows(stats ?? null, model?.usage_profile)} onExplore={setExplorer} />
            </View>
          )}
        </>
      ),
    },
    ...(sim?.outlook || (remote && !isSim)
      ? [
          {
            key: 'outlook',
            label: 'Outlook',
            render: () => (
              <View style={styles.body}>
                {sim?.outlook ?? null}
                {!isSim
                  ? (bodyGate ?? (
                      <View style={styles.section}>
                        <PlayerTrendsPanel playerId={player.player_id} yearsInLeague={bio?.years_in_league ?? null} />
                      </View>
                    ))
                  : null}
              </View>
            ),
          },
        ]
      : []),
    ...(remote
      ? [
          {
            key: 'stats',
            label: 'Stats',
            render: () =>
              bodyGate ?? (
                <View style={styles.body}>
                  {sim?.stats ?? null}
                  <UsageBlock profile={model?.usage_profile} position={stats?.position ?? player.position} onExplore={setExplorer} />
                  <SeasonStatsRows stats={stats ?? null} usageProfile={model?.usage_profile} onExplore={setExplorer} />
                  {stats && stats.college.length > 0 ? (
                    <View style={styles.section}>
                      <SectionHeading title="College" />
                      <View style={styles.tileGrid}>
                        {stats.college.map((item) => (
                          <MetricCard key={item.label} label={item.label} value={item.value || null} percentile={item.percentile ?? null} />
                        ))}
                      </View>
                    </View>
                  ) : null}
                </View>
              ),
          },
          {
            key: 'profile',
            label: 'Profile',
            render: () =>
              bodyGate ?? (
                <View style={styles.body}>
                  {awards.length > 0 ? (
                    <Section title="Awards">
                      <AwardsStrip awards={awards} />
                    </Section>
                  ) : null}
                  {bioRows.length > 0 ? (
                    <Section title="Bio">
                      <View style={styles.tileGrid}>
                        {bioRows.map(([label, value]) => (
                          <MetricCard key={label} label={label} value={value} />
                        ))}
                      </View>
                    </Section>
                  ) : null}
                </View>
              ),
          },
        ]
      : []),
    ...(sim?.scouting ? [{ key: 'scouting', label: 'Scouting', render: () => <>{sim.scouting}</> }] : []),
    ...(sim?.history ? [{ key: 'history', label: 'History', render: () => <>{sim.history}</> }] : []),
    ]),
  });

  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close player quick view">
        <SwipeDismissCard style={[styles.sheet, snap === 'peek' ? styles.sheetPeek : styles.sheetFull]} onDismiss={onClose} testID="player-quick-view">
          <View
            style={styles.grip}
            accessible
            accessibilityRole="button"
            accessibilityLabel={snap === 'peek' ? 'Expand player sheet' : 'Shrink player sheet'}
            onStartShouldSetResponder={() => true}
            onResponderGrant={(e) => {
              gripStart.current = { y: e.nativeEvent.pageY, t: Date.now() };
            }}
            onResponderRelease={(e) => {
              const start = gripStart.current;
              gripStart.current = null;
              if (!start) return;
              const dy = e.nativeEvent.pageY - start.y;
              const next = Math.abs(dy) < 6 ? (snap === 'peek' ? 'full' : 'peek') : nextSheetSnap(snap, dy, dy / Math.max(1, Date.now() - start.t));
              if (next !== snap) setSnap(next);
            }}
          >
            <View style={styles.gripBar} />
          </View>
          <SheetScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false} stickyHeaderIndices={[2]}>
            {/* Top bar: source label left, round close right (web .pqv-topbar). */}
            <View style={styles.topBar}>
              <AppText style={styles.kicker} numberOfLines={1}>
                {request.sourceLabel ?? ''}
              </AppText>
              <Pressable
                onPress={onClose}
                hitSlop={10}
                style={styles.closeButton}
                accessibilityRole="button"
                accessibilityLabel="Close"
              >
                <Ionicons name="close" size={18} color={colors.textSecondary} />
              </Pressable>
            </View>

            <PlayerHero
              playerId={player.player_id}
              avatarId={remote ? player.player_id : null}
              tier={scoped.tier}
              tierLabel={scoped.tier ? tierIdentity.semanticLabel : null}
              tierColor={tierIdentity.color}
              name={name}
              position={position}
              team={team}
              age={age}
              score={player.score ?? resolved?.value_score ?? null}
              valueNote={request.valueNote ?? resolved?.value_note}
              valueLabel={request.valueLabel ?? null}
              byeWeek={realWorld.showBye ? (resolved?.bye_week ?? null) : null}
              onByeThisWeek={realWorld.showBye ? (resolved?.on_bye_this_week ?? false) : false}
              unavailable={availability?.unavailable ?? false}
              rookie={rookieBadge(bio)}
              overallRating={overallRating}
              ringColor={overallRating != null ? overallRatingColor(overallRating, colors) : colors.accent}
              usageTrend={model?.usage_trend ?? null}
              simTiles={sim?.heroTiles ?? null}
              usageLoading={loading}
              valueChart={asOf == null && historyQuery.data && ratingHistoryCaption(historyQuery.data) ? <PlayerValueHistory history={historyQuery.data} /> : null}
              ovrChart={
                hasSubRatings ? (
                  <>
                    <ModelRadarChart ratings={subRatings} />
                    {subRatings.every((item) => item.rating != null) ? null : <SubRatingRow ratings={subRatings} size="md" />}
                  </>
                ) : null
              }
            >
              {ranks || (realWorld.showDepthChartNote && model?.depth_chart_note) ? (
                <View style={styles.footnote}>
                  {ranks ? <AppText style={styles.rankLine}>{ranks}</AppText> : null}
                  {realWorld.showDepthChartNote && model?.depth_chart_note ? <AppText style={styles.note}>{model.depth_chart_note}</AppText> : null}
                </View>
              ) : null}
              {showSignals ? (
                <View style={styles.signalRow}>
                  {scoped.opportunityLabel ? (
                    <ToneBadge label={scoped.opportunityLabel} color={colors.textSecondary} size="xs" />
                  ) : null}
                  {headerTags.length > 0 ? (
                    <>
                      <PlayerBadges badges={headerTags.map((tag) => badgeFromTag(tag))} max={6} showDetail onLegend={() => setLegendOpen(true)} />
                      {headerTags.filter((tag) => !badgeFromTag(tag)).map((tag) => (
                        <ToneBadge key={tag.key} label={tag.label} color={tagToneColor(tag.tone, colors)} size="xs" shrink />
                      ))}
                    </>
                  ) : injury ? (
                    badgeFromInjury(injury) ? (
                      <PlayerBadges badges={[{ kind: badgeFromInjury(injury)!, detail: injury }]} showDetail onLegend={() => setLegendOpen(true)} />
                    ) : (
                      <ToneBadge
                        label={`Health: ${injury}`}
                        color={injuryTone(player.injury_status) === 'danger' ? colors.danger : colors.warning}
                        size="xs"
                      />
                    )
                  ) : null}
                  <BadgeLegendSheet open={legendOpen} onClose={() => setLegendOpen(false)} />
                </View>
              ) : null}
              {mismatch ? <AppText style={styles.note}>{mismatch}</AppText> : null}
              {usageCaption ? <AppText style={styles.note}>{usageCaption}</AppText> : null}
            </PlayerHero>

            {/* Sticky tab strip: child index 2 (top bar, hero, strip), so keep those three as direct children. */}
            <View style={styles.stickyTabs}>{pqvTabs.bar}</View>
            {pqvTabs.panel}

            {/* Actions row (web .pqv-actions): league actions, then the
                profile / waivers destinations. */}
            <View style={styles.actions}>
              {actionsLeague && remote ? (
                <PlayerLeagueActions
                  player={player}
                  leagueId={actionsLeague.leagueId}
                  leagueName={actionsLeague.leagueName}
                  onNavigate={onClose}
                  hideAddToTrade={insideTradeAnalyzer()}
                />
              ) : null}
              <View style={styles.actionButtons}>
                {onWaivers ? (
                  <Button label="View on Waivers" variant="secondary" onPress={openWaivers} style={styles.actionButton} />
                ) : null}
                {target && remote ? <Button label="Open Full Profile" onPress={openFullProfile} style={styles.actionButton} /> : null}
              </View>
            </View>
            <ValuesCredit />
          </SheetScrollView>
        </SwipeDismissCard>
      </Pressable>
      {explorer ? (
        <PercentileExplorerSheet
          playerId={player.player_id}
          statKey={explorer.key}
          statLabel={explorer.label}
          leagueId={request.league?.leagueId ?? fallback?.leagueId ?? null}
          onClose={() => setExplorer(null)}
          onOpenPlayer={openExplorerPlayer}
        />
      ) : null}
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    // Sheet fill is `surface`, not `backgroundElevated`: the elevated tier is
    // #3d4248 in dark (web --color-surface-raised, meant for small raised
    // controls), which painted the whole sheet a flat mid-gray lighter than
    // the near-black app. `surface` keeps the card tiers inside it readable.
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      minHeight: sheetHeight.min,
      maxHeight: sheetHeight.max,
    },
    sheetPeek: { minHeight: '56%', maxHeight: '56%' },
    sheetFull: { minHeight: '92%', maxHeight: '92%' },
    grip: { height: 24, alignItems: 'center', justifyContent: 'center' },
    gripBar: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.borderStrong },
    stickyTabs: { backgroundColor: colors.surface, paddingVertical: spacing.xs },
    content: { padding: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
    topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 28 },
    kicker: { flex: 1, fontSize: 12.5, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary, textTransform: 'uppercase' },
    closeButton: {
      width: 28,
      height: 28,
      borderRadius: radii.pill,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
    },
    footnote: { gap: 2 },
    rankLine: { fontSize: 13.5, fontWeight: '600', color: colors.textSecondary },
    note: { fontSize: 13.5, lineHeight: 19, color: colors.textTertiary },
    signalRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.xs },
    body: { gap: spacing.lg },
    section: { gap: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing.md },
    statGroup: { gap: spacing.xs },
    groupTitle: { fontSize: 13.5, fontWeight: '700', color: colors.textSecondary },
    tileGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    muted: { fontSize: 14.5, color: colors.textSecondary },
    actionButtons: { flexDirection: 'row', gap: spacing.sm },
    actionButton: { flex: 1 },
    actions: {
      gap: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
      paddingTop: spacing.md,
    },
  });
}
