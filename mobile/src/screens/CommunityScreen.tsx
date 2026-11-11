import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useHeaderHeight } from '@react-navigation/elements';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SharedTradesFeed from '../components/SharedTradesFeed';
import ValuesCredit from '../components/ValuesCredit';
import { api, type SharedCommunityTrade } from '../lib/api';
import { useLastLeague } from '../lib/useLastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import ErrorState from '../components/ErrorState';

type Props = NativeStackScreenProps<RootStackParamList, 'Community'>;

/**
 * Community: the trades other users chose to share. Web has this as its own
 * nav row; in the app the same feed (the same SharedTradesFeed, the same
 * GET /v1/community/shared-trades) lived only at the bottom of Trade History,
 * four taps deep (UX audit 2026-11-03). This screen is that feed on its own,
 * reachable from the orb. Trade History keeps its copy at the bottom.
 */
export default function CommunityScreen({ navigation }: Props) {
  const lastLeague = useLastLeague();
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [shared, setShared] = useState<{ available: boolean; trades: SharedCommunityTrade[] } | null>(null);
  const [failed, setFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh: boolean) => {
    if (isRefresh) setRefreshing(true);
    setFailed(false);
    try {
      const r = await api.getSharedCommunityTrades();
      setShared({ available: Boolean(r.available), trades: r.trades });
    } catch {
      setFailed(true);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  if (!shared && !failed) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />}
      >
        <ScreenInfoNote text="Trades other users chose to share from the Trade Analyzer. Names are never shown, only a display name they picked. You can share your own from a trade verdict, and delete it any time." />
        {failed ? (
          <ErrorState compact title="Couldn't load the Community feed" onRetry={() => void load(false)} />
        ) : shared && shared.available ? (
          <SharedTradesFeed
            available={shared.available}
            trades={shared.trades}
            onDelete={(id) => {
              setShared((cur) => (cur ? { ...cur, trades: cur.trades.filter((t) => t.id !== id) } : cur));
              void api.deleteSharedCommunityTrade(id).catch(() => {});
            }}
            onReport={(id) => void api.reportSharedCommunityTrade(id).catch(() => {})}
          />
        ) : (
          <EmptyState
            icon="people-circle-outline"
            title="Community isn't available yet"
            subtitle="Shared trades will show up here once sharing is switched on."
            actionLabel={lastLeague ? 'Analyze a trade of your own' : undefined}
            onPressAction={
              lastLeague
                ? () =>
                    navigation.navigate('Trades', {
                      leagueId: lastLeague.leagueId,
                      leagueName: lastLeague.leagueName,
                      initialTab: 'make',
                    })
                : undefined
            }
          />
        )}
        <ValuesCredit />
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    center: { flex: 1, backgroundColor: 'transparent' },
    content: { paddingHorizontal: spacing.lg, gap: spacing.md },
    error: { color: colors.danger, textAlign: 'center', marginTop: spacing.md },
  });
}
