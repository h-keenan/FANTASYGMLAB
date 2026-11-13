import React, { useEffect, useMemo, useState } from 'react';
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
import PlayerTrendsPanel from './PlayerTrendsPanel';
import SectionHeading from './SectionHeading';
import SkeletonBlock, { SkeletonChart } from './SkeletonBlock';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import PlayerValueHistory from './PlayerValueHistory';
import { ratingHistoryCaption } from '../lib/valueHistoryPresentation';
import SubRatingRow from './SubRatingRow';
import ToneBadge from './ToneBadge';
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
import { radii, scrim, spacing, type ThemeColors } from '../theme';

type ExplorerTarget = { key: string; label: string };

/** One web-PQV section: hairline top rule, small caps heading. */
function Section({ title, icon, children }: { title: string; icon?: React.ComponentProps<typeof SectionHeading>['icon']; children: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.section}>
      <SectionHeading title={title} icon={icon} />
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

export default function PlayerQuickViewSheet({
  request,
  onClose,
  simOverlay,
  remote = true,
}: {
  request: QuickViewRequest;
  onClose: () => void;
  /** Fantasy Sim: game-specific sections rendered right under the hero (mirrors web PlayerQuickView). Omit everywhere else. */
  simOverlay?: React.ReactNode;
  /** false for a synthetic sim player with no real data behind the id: same layout, no remote fetches. */
  remote?: boolean;
}) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { openPlayer } = usePlayerQuickView();
  const { player } = request;
  const [explorer, setExplorer] = useState<ExplorerTarget | null>(null);
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
    enabled: detailQuery.isSuccess,
    staleTime: 2 * 60 * 1000,
  });
  const newsLoading = detailQuery.isSuccess && newsQuery.isPending;

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
  const stats = detail?.stats ?? null;
  const model = detail?.model ?? null;
  const bio = detail?.bio ?? null;
  const awards = awardsQuery.data?.ok ? awardsQuery.data.awards : [];

  const name = player.name || resolved?.name || `Player ${player.player_id}`;
  const position = player.position || resolved?.position || null;
  const team = player.team || resolved?.team || null;
  const age = player.age ?? resolved?.age ?? null;
  const overallRating = player.overall_rating ?? stats?.overall_rating ?? resolved?.overall_rating ?? null;
  // The server's availability block wins; the row's raw status only drives
  // the chip (with a clean label) until it arrives.
  const availability = resolved?.availability ?? null;
  const injury = availability ? null : cleanInjuryLabel(player.injury_status);
  const target = fullProfileTarget(request, fallback);
  // League-less opens (News) borrow the last-used league for the trade
  // shortcuts too, same as Full Profile; none known means no actions.
  const actionsLeague = request.league ?? fallback;
  const loading = remote && detailQuery.isPending;

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

  const bioRows = bio
    ? ([
        ['Experience', bio.years_in_league],
        ['Draft capital', bio.draft_capital],
        ['College', bio.college],
        ['Height', bio.height],
        ['Weight', bio.weight],
        ['Bye week', bio.bye_week],
        ['Contract', bio.contract_status],
      ] as const).filter(([, v]) => Boolean(v))
    : [];

  const tierIdentity = resolvePlayerTier(scoped.tier, isDark);
  const mismatch = tierOpportunityMismatchCaption(scoped.tier, scoped.opportunityLabel);
  const usageCaption = opportunityUsageCaption(scoped.opportunityLabel, model?.usage_trend ?? null);
  const ranks = rankLine(position, scoped.overallRank, scoped.positionRank);
  const subRatings = model ? playerSubRatings(model) : [];
  const hasSubRatings = subRatings.some((item) => item.rating != null);
  const showSignals = !!scoped.opportunityLabel || !!injury;

  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close player quick view">
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose} testID="player-quick-view">
          <SheetScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
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
              tier={scoped.tier}
              tierLabel={scoped.tier ? tierIdentity.semanticLabel : null}
              tierColor={tierIdentity.color}
              name={name}
              position={position}
              team={team}
              age={age}
              score={player.score ?? resolved?.value_score ?? null}
              valueNote={resolved?.value_note}
              byeWeek={resolved?.bye_week ?? null}
              onByeThisWeek={resolved?.on_bye_this_week ?? false}
              unavailable={availability?.unavailable ?? false}
              rookie={rookieBadge(bio)}
              overallRating={overallRating}
              ringColor={overallRating != null ? overallRatingColor(overallRating, colors) : colors.accent}
              usageTrend={model?.usage_trend ?? null}
              usageLoading={loading}
              valueChart={historyQuery.data && ratingHistoryCaption(historyQuery.data) ? <PlayerValueHistory history={historyQuery.data} /> : null}
              ovrChart={
                hasSubRatings ? (
                  <>
                    <ModelRadarChart ratings={subRatings} />
                    {subRatings.every((item) => item.rating != null) ? null : <SubRatingRow ratings={subRatings} size="md" />}
                  </>
                ) : null
              }
            >
              {ranks || model?.depth_chart_note ? (
                <View style={styles.footnote}>
                  {ranks ? <AppText style={styles.rankLine}>{ranks}</AppText> : null}
                  {model?.depth_chart_note ? <AppText style={styles.note}>{model.depth_chart_note}</AppText> : null}
                </View>
              ) : null}
              {showSignals ? (
                <View style={styles.signalRow}>
                  {scoped.opportunityLabel ? (
                    <ToneBadge label={scoped.opportunityLabel} color={colors.textSecondary} size="xs" />
                  ) : null}
                  {injury ? (
                    <ToneBadge
                      label={`Health: ${injury}`}
                      color={injuryTone(player.injury_status) === 'danger' ? colors.danger : colors.warning}
                      size="xs"
                    />
                  ) : null}
                </View>
              ) : null}
              {mismatch ? <AppText style={styles.note}>{mismatch}</AppText> : null}
              {usageCaption ? <AppText style={styles.note}>{usageCaption}</AppText> : null}
            </PlayerHero>

            {simOverlay}

            {availability ? (
              <AvailabilityBlock
                availability={availability}
                injuryItem={newsQuery.data?.injury_item ?? null}
                newsLoading={newsLoading}
              />
            ) : null}
            {detail && remote ? (
              <LatestNewsSection
                items={newsQuery.data ? newsQuery.data.items : null}
                loading={newsLoading}
                onSeeAll={openPlayerNews}
                hideItem={availability ? newsQuery.data?.injury_item ?? null : null}
              />
            ) : null}

            {loading ? (
              <View style={styles.body}>
                <SkeletonBlock height={64} />
                <SkeletonChart />
                <SkeletonBlock height={90} />
                <SkeletonBlock height={90} />
              </View>
            ) : !remote ? null : detailQuery.isError || !detail ? (
              <AppText style={styles.muted}>Couldn&apos;t load this player&apos;s detail right now.</AppText>
            ) : (
              <View style={styles.body}>
                {model?.decision_fit_narrative ? <DecisionFitCard narrative={model.decision_fit_narrative} /> : null}
                <HeadlineTiles rows={headlineRows(stats ?? null, model?.usage_profile)} onExplore={setExplorer} />
                <View style={styles.section}>
                  <PlayerTrendsPanel playerId={player.player_id} yearsInLeague={bio?.years_in_league ?? null} />
                </View>
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
                {/* Value history and the Model radar live behind a tap on the Value and
                    Player score tiles in the hero (TapForWhy), as on web. */}
              </View>
            )}

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
      maxHeight: '92%',
    },
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
