import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import { api } from '../lib/api';
import { tradeOddsView, type WhatIfTone } from '../lib/gamesPresentation';
import { queryKeys } from '../lib/queryKeys';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

/**
 * "Effect on your odds" row for a trade (Analyzer verdict and the Trade Hub /
 * Finder idea details). Fetched lazily from POST .../trade-odds-effect (the
 * Season Simulator re-run with the post-trade roster) so the verdict itself is
 * never slowed. Renders nothing when there is nothing real to show; Free
 * accounts get a one-line Premium pointer. Mirrors web-next's TradeOddsEffect.
 */

export interface OddsAsset {
  asset_type?: string;
  player_id?: string | null;
}

export function splitOddsAssets(assets: OddsAsset[]): { ids: string[]; hasPicks: boolean } {
  const ids: string[] = [];
  let hasPicks = false;
  for (const asset of assets) {
    if (asset.asset_type === 'pick') hasPicks = true;
    else if (asset.player_id) ids.push(String(asset.player_id));
  }
  return { ids, hasPicks };
}

export default function TradeOddsEffect({
  leagueId,
  send,
  receive,
  hasPicks: extraPicks = false,
}: {
  leagueId: string;
  send: OddsAsset[];
  receive: OddsAsset[];
  /** True when the package also holds picks the caller could not list in send/receive. */
  hasPicks?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const sendSplit = splitOddsAssets(send);
  const receiveSplit = splitOddsAssets(receive);
  const hasPicks = extraPicks || sendSplit.hasPicks || receiveSplit.hasPicks;
  const sendKey = [...sendSplit.ids].sort().join(',');
  const receiveKey = [...receiveSplit.ids].sort().join(',');

  const query = useQuery({
    queryKey: queryKeys.tradeOddsEffect(leagueId, sendKey, receiveKey, hasPicks),
    queryFn: () =>
      api.postTradeOddsEffect(leagueId, [
        { send_player_ids: sendSplit.ids, receive_player_ids: receiveSplit.ids, has_picks: hasPicks },
      ]),
    enabled: Boolean(sendKey || receiveKey),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  const response = query.data;
  if (!response) return null;
  if (response.reason === 'premium_required') {
    return (
      <PressableScale onPress={() => navigation.navigate('Paywall')} testID="trade-odds-upsell">
        <AppText style={styles.caption}>
          {response.upsell?.title ?? 'See how a trade moves your odds'}. <AppText style={styles.upgrade}>Pro</AppText>
        </AppText>
      </PressableScale>
    );
  }
  const view = tradeOddsView(response.reason ? null : response.results[0]);
  if (!view) return null;
  const toneColor: Record<WhatIfTone, string> = {
    positive: colors.success,
    negative: colors.danger,
    neutral: colors.textSecondary,
  };
  return (
    <View testID="trade-odds-effect" style={styles.wrap}>
      <AppText style={styles.label}>EFFECT ON YOUR ODDS</AppText>
      <AppText style={[styles.headline, { color: toneColor[view.tone] }]}>{view.headline}</AppText>
      {view.titleLine ? <AppText style={styles.title}>{view.titleLine}</AppText> : null}
      <AppText style={styles.caption}>
        {view.detail}
        {view.notes.length ? `. ${view.notes.join(' ')}` : ''}
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { marginTop: spacing.sm, gap: 2 },
    label: { fontSize: 12.5, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary },
    headline: { fontSize: 15.5, fontWeight: '700' },
    title: { fontSize: 14.5, color: colors.textSecondary },
    caption: { fontSize: 12.5, color: colors.textTertiary },
    upgrade: { fontSize: 12.5, fontWeight: '700', color: colors.premium },
  });
}
