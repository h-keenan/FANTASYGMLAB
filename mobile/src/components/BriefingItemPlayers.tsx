import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactPlayerModule from './CompactPlayerModule';
import TradeAssetRow from './TradeAssetRow';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardItem } from '../lib/api';
import { hasTradePackage, signalPlayers, type SignalPlayer } from '../lib/portfolioSignals';
import { spacing, type ThemeColors } from '../theme';

/**
 * The compact player-card visual for a briefing item: a give/get trade
 * package, or the route player plus every other player the text names.
 * Mirrors web-next's BriefingItemPlayers (same data rules, shared with
 * Portfolio's per-league signal rows) so a signal shows real headshots on
 * both surfaces instead of a text dump. Renders nothing when the item names
 * no players (never fabricated).
 */
export default function BriefingItemPlayers({
  item,
  onPressPlayer,
  excludePlayerId,
}: {
  item: DashboardItem;
  onPressPlayer?: (player: SignalPlayer) => void;
  /** Skip this player (a row that already renders the route player itself
   * passes its id so only the other mentioned players are added). */
  excludePlayerId?: string | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const pkg = item.presentation?.trade_package;

  if (hasTradePackage(item) && pkg) {
    return (
      <View style={styles.stack}>
        <AppText style={styles.sideLabel}>YOU SEND</AppText>
        {pkg.send.map((asset, index) => (
          <TradeAssetRow key={`send-${index}`} asset={asset} />
        ))}
        <AppText style={styles.sideLabel}>YOU GET</AppText>
        {pkg.receive.map((asset, index) => (
          <TradeAssetRow key={`receive-${index}`} asset={asset} />
        ))}
      </View>
    );
  }

  const players = signalPlayers(item).filter((p) => !excludePlayerId || p.player_id !== excludePlayerId);
  if (players.length === 0) return null;
  return (
    <View style={styles.stack}>
      {players.map((player) => (
        <CompactPlayerModule
          key={player.player_id}
          playerId={player.player_id}
          name={player.name}
          position={player.position || null}
          team={player.team || null}
          tier={player.tier || null}
          value={player.score}
          valueLabel="VALUE"
          contextLine={player.injury_status || null}
          onPress={onPressPlayer ? () => onPressPlayer(player) : undefined}
        />
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.sm, marginTop: spacing.xs },
    sideLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4, color: colors.textTertiary },
  });
}
