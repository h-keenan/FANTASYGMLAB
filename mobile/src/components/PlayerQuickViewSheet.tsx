import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import AwardsStrip from './AwardsStrip';
import Button from './Button';
import MetricCard from './MetricCard';
import OverallRatingBadge from './OverallRatingBadge';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import SkeletonBlock from './SkeletonBlock';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import SubRatingRow from './SubRatingRow';
import TierBadge from './TierBadge';
import ToneBadge from './ToneBadge';
import UsageTrendPill from './UsageTrendPill';
import WeeklyPointsChart from './WeeklyPointsChart';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type QuickViewStatItem } from '../lib/api';
import { injuryAbbreviation } from '../lib/injuryDisplay';
import { getLastLeague } from '../lib/lastLeague';
import {
  fullProfileTarget,
  leagueScopedIdentity,
  type QuickViewLeague,
  type QuickViewRequest,
} from '../lib/playerQuickView';
import { queryKeys } from '../lib/queryKeys';
import { isOnWaiverList } from '../lib/waiverHighlight';
import { playerSubRatings } from '../lib/subRatings';
import { navigationRef } from '../navigation/navigationRef';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

function StatTiles({ title, items }: { title: string; items: QuickViewStatItem[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!items.length) return null;
  return (
    <View style={styles.section}>
      <SectionHeading title={title} />
      <View style={styles.tileGrid}>
        {items.map((item) => (
          <MetricCard
            key={item.label}
            label={item.label}
            value={item.value || null}
            percentile={item.percentile ?? null}
          />
        ))}
      </View>
    </View>
  );
}

function WeeklyPoints({ playerId }: { playerId: string }) {
  const query = useQuery({
    queryKey: [...queryKeys.playerQuickView(playerId), 'weekly'],
    queryFn: () => api.getPlayerWeeklyStats(playerId),
    staleTime: 5 * 60 * 1000,
  });
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const weeks = query.data?.weeks ?? [];
  if (!weeks.length) return null;
  return (
    <View style={styles.section}>
      <SectionHeading title="Points by week" icon="trending-up-outline" />
      <WeeklyPointsChart weeks={weeks} />
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player } = request;
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
  const season = stats?.seasons?.[0] ?? null;

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

  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close player quick view">
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose} testID="player-quick-view">
          <SheetScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
            <View style={styles.hero}>
              <PlayerAvatar playerId={player.player_id} size={64} tier={scoped.tier} />
              <View style={styles.heroText}>
                {request.sourceLabel ? <AppText style={styles.kicker}>{request.sourceLabel}</AppText> : null}
                <AppText style={styles.name} numberOfLines={2}>
                  {name}
                </AppText>
                <View style={styles.metaRow}>
                  <PositionBadge position={position} size="sm" />
                  {team ? <AppText style={styles.meta}>{team}</AppText> : null}
                  {age != null ? <AppText style={styles.meta}>{`Age ${age}`}</AppText> : null}
                </View>
              </View>
              <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close">
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </Pressable>
            </View>

            <View style={styles.chipRow}>
              <OverallRatingBadge rating={overallRating} size="md" positionRank={scoped.positionRank} />
              <TierBadge storedTier={scoped.tier} size="md" />
              {scoped.overallRank != null ? <ToneBadge label={`#${scoped.overallRank} overall`} color={colors.textSecondary} size="xs" /> : null}
              {model?.usage_trend ? <UsageTrendPill trend={model.usage_trend} /> : null}
              {injury ? <ToneBadge label={`Health: ${injury}`} color={colors.danger} size="xs" /> : null}
              {scoped.opportunityLabel ? <ToneBadge label={scoped.opportunityLabel} color={colors.accent} size="xs" /> : null}
            </View>

            {loading ? (
              <View style={styles.section}>
                <SkeletonBlock height={14} />
                <SkeletonBlock height={90} style={styles.skeletonGap} />
                <SkeletonBlock height={90} style={styles.skeletonGap} />
              </View>
            ) : detailQuery.isError || !detail ? (
              <AppText style={styles.muted}>Couldn&apos;t load this player&apos;s detail right now.</AppText>
            ) : (
              <>
                {model?.decision_fit_narrative ? (
                  <AppText style={styles.narrative}>{model.decision_fit_narrative}</AppText>
                ) : null}
                <WeeklyPoints playerId={player.player_id} />
                {season ? (
                  <>
                    <AppText style={styles.seasonLabel}>
                      {season.label}
                      {season.games != null ? ` · ${season.games} games` : ''}
                    </AppText>
                    <StatTiles title="Fantasy" items={season.fantasy} />
                    <StatTiles title="Production" items={season.key_stats} />
                    <StatTiles title="Usage" items={season.usage} />
                  </>
                ) : null}
                {awards.length > 0 ? (
                  <View style={styles.section}>
                    <SectionHeading title="Awards" />
                    <AwardsStrip awards={awards} />
                  </View>
                ) : null}
                {bioRows.length > 0 ? (
                  <View style={styles.section}>
                    <SectionHeading title="Bio" />
                    <View style={styles.tileGrid}>
                      {bioRows.map(([label, value]) => (
                        <MetricCard key={label} label={label} value={value} />
                      ))}
                    </View>
                  </View>
                ) : null}
                {model ? (
                  <View style={styles.section}>
                    <SectionHeading title="Model" />
                    <SubRatingRow ratings={playerSubRatings(model)} size="md" />
                  </View>
                ) : null}
              </>
            )}

            {onWaivers ? (
              <Button label="View on Waivers" variant="secondary" onPress={openWaivers} style={styles.cta} />
            ) : null}
            {target ? (
              <Button label="Full profile" onPress={openFullProfile} style={styles.cta} />
            ) : null}
          </SheetScrollView>
        </SwipeDismissCard>
      </Pressable>
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
      maxHeight: '88%',
    },
    content: { padding: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
    hero: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    heroText: { flex: 1, gap: 4 },
    kicker: { fontSize: 10, fontWeight: '700', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
    name: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    meta: { fontSize: 12, color: colors.textSecondary },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.xs },
    section: { gap: spacing.sm },
    skeletonGap: { marginTop: spacing.sm },
    tileGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    narrative: { fontSize: 14, lineHeight: 20, color: colors.textSecondary },
    seasonLabel: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 13, color: colors.textSecondary },
    cta: { marginTop: spacing.sm },
  });
}
