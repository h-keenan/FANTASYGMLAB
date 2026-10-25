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
import PlayerTrendsPanel from './PlayerTrendsPanel';
import SectionHeading from './SectionHeading';
import SkeletonBlock, { SkeletonChart } from './SkeletonBlock';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import SubRatingRow from './SubRatingRow';
import ToneBadge from './ToneBadge';
import ValuesCredit from './ValuesCredit';
import { useThemeMode } from '../context/ThemeModeContext';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { api, type QuickViewStatItem } from '../lib/api';
import { injuryAbbreviation, injuryTone } from '../lib/injuryDisplay';
import { getLastLeague } from '../lib/lastLeague';
import { explorerStatKey, type ExplorerPlayer } from '../lib/percentileExplorer';
import { overallRatingColor } from '../lib/percentile';
import { resolvePlayerTier } from '../lib/playerTier';
import {
  fullProfileTarget,
  leagueScopedIdentity,
  stubPlayer,
  type QuickViewLeague,
  type QuickViewRequest,
} from '../lib/playerQuickView';
import { rankLine, seasonStatGroups, tierOpportunityMismatchCaption } from '../lib/playerQuickViewPresentation';
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

function StatTiles({
  title,
  items,
  onExplore,
}: {
  title: string;
  items: QuickViewStatItem[];
  onExplore?: (target: ExplorerTarget) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!items.length) return null;
  return (
    <View style={styles.statGroup}>
      <AppText style={styles.groupTitle}>{title}</AppText>
      <View style={styles.tileGrid}>
        {items.map((item) => {
          // Tiles that carry a percentile open the Percentile Explorer, same
          // as web's StatGroup and Player Detail.
          const key = onExplore && item.percentile != null ? explorerStatKey(item.label) : null;
          return (
            <MetricCard
              key={item.label}
              label={item.label}
              value={item.value || null}
              percentile={item.percentile ?? null}
              onPress={key && onExplore ? () => onExplore({ key, label: item.label }) : undefined}
            />
          );
        })}
      </View>
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
export default function PlayerQuickViewSheet({ request, onClose }: { request: QuickViewRequest; onClose: () => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { openPlayer } = usePlayerQuickView();
  const { player } = request;
  const [explorer, setExplorer] = useState<ExplorerTarget | null>(null);
  const scoped = leagueScopedIdentity(request);

  const detailQuery = useQuery({
    queryKey: queryKeys.playerQuickView(player.player_id),
    queryFn: () => api.getPlayerQuickView(player.player_id),
  });
  const awardsQuery = useQuery({
    queryKey: [...queryKeys.playerQuickView(player.player_id), 'awards'],
    queryFn: () => api.getPlayerAwards(player.player_id),
    staleTime: 5 * 60 * 1000,
  });

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
    if (request.league) return;
    let cancelled = false;
    void getLastLeague().then((last) => {
      if (!cancelled && last) setFallback({ leagueId: last.leagueId, leagueName: last.leagueName });
    });
    return () => {
      cancelled = true;
    };
  }, [request.league]);

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
  const injury = injuryAbbreviation(player.injury_status);
  const target = fullProfileTarget(request, fallback);
  const loading = detailQuery.isPending;

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
              overallRating={overallRating}
              ringColor={overallRating != null ? overallRatingColor(overallRating, colors) : colors.accent}
              usageTrend={model?.usage_trend ?? null}
              usageLoading={loading}
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
                      color={injuryTone(player.injury_status) === 'danger' ? colors.danger : colors.premium}
                      size="xs"
                    />
                  ) : null}
                </View>
              ) : null}
              {mismatch ? <AppText style={styles.note}>{mismatch}</AppText> : null}
            </PlayerHero>

            {loading ? (
              <View style={styles.body}>
                <SkeletonBlock height={64} />
                <SkeletonChart />
                <SkeletonBlock height={90} />
                <SkeletonBlock height={90} />
              </View>
            ) : detailQuery.isError || !detail ? (
              <AppText style={styles.muted}>Couldn&apos;t load this player&apos;s detail right now.</AppText>
            ) : (
              <View style={styles.body}>
                {model?.decision_fit_narrative ? <DecisionFitCard narrative={model.decision_fit_narrative} /> : null}
                <View style={styles.section}>
                  <PlayerTrendsPanel playerId={player.player_id} yearsInLeague={bio?.years_in_league ?? null} />
                </View>
                {(stats?.seasons ?? []).map((seasonItem) => (
                  <View key={seasonItem.label} style={styles.section}>
                    <SectionHeading
                      title={`${seasonItem.label}${seasonItem.games != null ? ` · ${seasonItem.games} games` : ''}`}
                    />
                    {seasonStatGroups(seasonItem).map((group) => (
                      <StatTiles key={group.title} title={group.title} items={group.items} onExplore={setExplorer} />
                    ))}
                  </View>
                ))}
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
                {/* Model is the last section, as on web: radar when every
                    axis has a rating, chip row otherwise. */}
                {hasSubRatings ? (
                  <Section title="Model">
                    <ModelRadarChart ratings={subRatings} />
                    {subRatings.every((item) => item.rating != null) ? null : (
                      <SubRatingRow ratings={subRatings} size="md" />
                    )}
                  </Section>
                ) : null}
              </View>
            )}

            {/* Actions row (web .pqv-actions): league actions, then the
                profile / waivers destinations. */}
            <View style={styles.actions}>
              {request.league ? (
                <PlayerLeagueActions
                  player={player}
                  leagueId={request.league.leagueId}
                  leagueName={request.league.leagueName}
                  onNavigate={onClose}
                />
              ) : null}
              {onWaivers ? (
                <Button label="View on Waivers" variant="secondary" onPress={openWaivers} />
              ) : null}
              {target ? <Button label="Open Full Profile" onPress={openFullProfile} /> : null}
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
          onClose={() => setExplorer(null)}
          onOpenPlayer={openExplorerPlayer}
        />
      ) : null}
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    // Solid elevated sheet, same treatment as every other bottom sheet.
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      maxHeight: '92%',
    },
    content: { padding: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
    topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 28 },
    kicker: { flex: 1, fontSize: 11, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary, textTransform: 'uppercase' },
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
    rankLine: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    note: { fontSize: 12, lineHeight: 17, color: colors.textTertiary },
    signalRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.xs },
    body: { gap: spacing.lg },
    section: { gap: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing.md },
    statGroup: { gap: spacing.xs },
    groupTitle: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
    tileGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    muted: { fontSize: 13, color: colors.textSecondary },
    actions: {
      gap: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
      paddingTop: spacing.md,
    },
  });
}
