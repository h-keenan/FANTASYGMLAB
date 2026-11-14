import React, { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import PlayerIdentityRow from './PlayerIdentityRow';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { api, type RankedPlayer, type ValueSignalItem } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { formatRatingDelta, signalReason, signalsStatusMessage } from '../lib/valueHistoryPresentation';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type Tab = 'buy_low' | 'sell_high';

function toRankedPlayer(item: ValueSignalItem): RankedPlayer {
  return {
    player_id: item.player_id,
    name: item.name,
    position: item.position,
    team: item.team,
    age: item.age,
    status: null,
    injury_status: item.injury_status,
    tier: null,
    score: null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
  };
}

/** Buy low / Sell high on Trade Hub: players whose value rating moved against
 * how they are producing, from the real daily rating snapshots. Hidden when
 * unreadable; states the real history span while it is still building.
 * Mirrors web's ValueSignalsCard. */
export default function ValueSignalsCard({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { openPlayer } = usePlayerQuickView();
  const [tab, setTab] = useState<Tab>('buy_low');
  const query = useQuery({
    queryKey: queryKeys.playerValueSignals(),
    queryFn: () => api.getPlayerValueSignals(),
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
  const data = query.data;
  if (!data || data.status === 'unavailable') return null;
  const status = signalsStatusMessage(data);
  const items = tab === 'buy_low' ? data.buy_low : data.sell_high;
  // Both tabs empty: collapse to one line instead of tabs over two empty lists.
  if (!status && data.buy_low.length === 0 && data.sell_high.length === 0) {
    return (
      <View style={styles.wrap} testID="value-signals">
        <SectionHeading title="Buy low / Sell high" />
        <AppText style={styles.note} testID="value-signals-none">
          No buy-low or sell-high candidates right now. Nobody clears both the value-trend and production bars.
        </AppText>
      </View>
    );
  }
  return (
    <View style={styles.wrap} testID="value-signals">
      <SectionHeading title="Buy low / Sell high" />
      <AppText style={styles.note}>Value rating trend against this season's production.</AppText>
      {status ? (
        <AppText style={styles.note}>{status}</AppText>
      ) : (
        <>
          <SegmentedTabBar
            options={[
              { key: 'buy_low' as Tab, label: `Buy low (${data.buy_low.length})` },
              { key: 'sell_high' as Tab, label: `Sell high (${data.sell_high.length})` },
            ]}
            active={tab}
            onChange={setTab}
          />
          {items.length === 0 ? (
            <AppText style={styles.note}>Nobody currently clears both the value-trend and production bars.</AppText>
          ) : (
            items.map((item) => (
              <PressableScale
                key={item.player_id}
                style={styles.row}
                onPress={() => openPlayer(toRankedPlayer(item), { leagueId, leagueName })}
              >
                <View style={styles.rowMain}>
                  <PlayerIdentityRow
                    playerId={item.player_id}
                    name={item.name}
                    position={item.position}
                    team={item.team}
                    injuryLabel={item.injury_status}
                    contextLine={signalReason(item)}
                  />
                </View>
                <AppText
                  style={[styles.delta, { color: item.signal === 'buy_low' ? colors.success : colors.danger }]}
                >
                  {formatRatingDelta(item.rating_change)}
                </AppText>
              </PressableScale>
            ))
          )}
          {data.method ? (
            <AppText style={styles.note}>
              {data.method} Based on {data.span_days} days of stored value history.
            </AppText>
          ) : null}
        </>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm, marginTop: spacing.lg },
    note: { fontSize: 13.5, color: colors.textTertiary },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      padding: spacing.sm,
      borderRadius: radii.md,
      backgroundColor: colors.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
    },
    rowMain: { flex: 1 },
    delta: { fontSize: 16.5, fontWeight: '800' },
  });
}
