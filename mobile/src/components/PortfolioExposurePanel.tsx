import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import PlayerIdentityRow from './PlayerIdentityRow';
import PremiumLock from './PremiumLock';
import SegmentedTabBar from './SegmentedTabBar';
import SkeletonBlock from './SkeletonBlock';
import DashboardStatRow from './DashboardStatRow';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { trackUse } from '../lib/analytics';
import { sortExposurePlayers, type ExposureSortKey } from '../lib/portfolioExposure';
import { queryKeys } from '../lib/queryKeys';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';

type SortKey = ExposureSortKey;

const SORT_OPTIONS: Array<{ key: SortKey; label: string }> = [
  { key: 'leagues', label: 'Most owned' },
  { key: 'value', label: 'Value' },
];

const percent = (share: number) => `${Math.round(share * 100)}%`;

/**
 * Portfolio's "Exposure" view (Pro): which players the caller owns across
 * their saved leagues, from GET /v1/portfolio/exposure. Mirrors web's
 * PortfolioExposureView. The server owns every number; this only sorts and
 * presents them. Tap a player for Player Detail, tap the count to see which
 * leagues.
 */
export default function PortfolioExposurePanel() {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [sort, setSort] = useState<SortKey>('leagues');
  const [expanded, setExpanded] = useState<string | null>(null);
  const query = useQuery({ queryKey: queryKeys.portfolioExposure(), queryFn: () => api.getPortfolioExposure() });
  const data = query.data ?? null;
  const players = useMemo(() => sortExposurePlayers(data?.exposure?.players ?? [], sort), [data, sort]);
  const exposureTier = data ? (data.is_premium ? 'pro' : 'free') : null;
  useEffect(() => {
    if (exposureTier) trackUse('player_exposure', 'viewed', { tier: exposureTier });
  }, [exposureTier]);

  if (query.isError && !data) {
    return <AppText style={styles.muted}>Could not load exposure. Try again in a moment.</AppText>;
  }
  if (!data) {
    return (
      <View style={styles.gap}>
        <SkeletonBlock width="100%" height={56} />
        <SkeletonBlock width="85%" height={40} />
        <SkeletonBlock width="70%" height={40} />
      </View>
    );
  }
  if (!data.is_premium) {
    return (
      <PremiumLock
        feature="exposure"
        title={data.upsell?.title ?? 'See your player exposure'}
        description={
          data.upsell?.body ??
          'Exposure is a Pro feature: which players you own across every league and how concentrated your portfolio is.'
        }
      />
    );
  }
  const exposure = data.exposure;
  if (!exposure) return <AppText style={styles.muted}>Save a league to see your exposure.</AppText>;

  const positions = exposure.by_position
    .filter((p) => p.share_of_value >= 0.01)
    .map((p) => `${p.position} ${percent(p.share_of_value)}`)
    .join(' · ');
  const skipped = data.skipped_leagues;

  return (
    <View style={styles.gap}>
      <DashboardStatRow
        style={{ marginBottom: 0 }}
        items={[
          { label: 'Leagues', value: String(exposure.league_count) },
          { label: 'Players', value: String(exposure.player_count) },
          { label: `Top ${exposure.concentration.top_n} share`, value: percent(exposure.concentration.top_share_of_value) },
        ]}
      />
      {positions ? <AppText style={styles.muted}>{`By value: ${positions}`}</AppText> : null}
      {skipped.length > 0 ? (
        <AppText style={styles.muted}>
          {`Not included: ${skipped.map((l) => l.league_name).join(', ')}${
            skipped.some((l) => l.reason === 'espn_not_supported') ? " (ESPN leagues aren't supported yet)" : ''
          }`}
        </AppText>
      ) : null}
      <SegmentedTabBar options={SORT_OPTIONS} active={sort} onChange={setSort} />
      <View>
        {players.map((player) => {
          const open = expanded === player.player_id;
          const firstLeague = player.leagues[0];
          return (
            <View key={player.player_id} style={styles.row}>
              <View style={styles.rowTop}>
                <View style={styles.identity}>
                  <PlayerIdentityRow
                    playerId={player.player_id}
                    name={player.name}
                    position={player.position}
                    team={player.team}
                    contextLine={`${percent(player.share_of_leagues)} of leagues`}
                    trailingValue={Math.round(player.value).toLocaleString()}
                    onPress={
                      firstLeague
                        ? () =>
                            openQuickView({
                                player_id: player.player_id,
                                name: player.name,
                                position: player.position,
                                team: player.team,
                                age: null,
                                status: null,
                                injury_status: null,
                                tier: null,
                                score: player.value,
                                overall_rank: null,
                                position_rank: null,
                                rank_unavailable_reason: null,
                                opportunity_label: null,
                              }, { leagueId: firstLeague.league_id, leagueName: firstLeague.league_name })
                        : undefined
                    }
                  />
                </View>
                <TouchableOpacity
                  onPress={() => setExpanded(open ? null : player.player_id)}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: open }}
                  accessibilityLabel={`${player.name} is in ${player.leagues_owned} of ${exposure.league_count} leagues`}
                  style={styles.countPill}
                >
                  <AppText style={styles.countText}>{`${player.leagues_owned}/${exposure.league_count}`}</AppText>
                </TouchableOpacity>
              </View>
              {open ? (
                <View style={styles.leagueList}>
                  {player.league_names.map((name) => (
                    <AppText key={name} style={styles.muted}>
                      {name}
                    </AppText>
                  ))}
                </View>
              ) : null}
            </View>
          );
        })}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    gap: { gap: spacing.md },
    muted: { fontSize: 12, color: colors.textSecondary },
    row: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border, paddingVertical: spacing.xs },
    rowTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    identity: { flex: 1 },
    countPill: {
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
    },
    countText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
    leagueList: { paddingLeft: spacing.xl, paddingBottom: spacing.xs, gap: 2 },
  });
}
