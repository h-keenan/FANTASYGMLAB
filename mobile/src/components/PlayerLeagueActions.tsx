import React, { useEffect, useMemo, useState } from 'react';
import { Alert, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type RankedPlayer } from '../lib/api';
import { tradeShortcutsFor } from '../lib/tradeShortcuts';
import { canBuildOffer } from '../lib/tradeOffer';
import { useRosterOwnership } from '../lib/useRosterOwnership';
import { navigationRef } from '../navigation/navigationRef';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The contextual league actions on Player Quick View (web twin:
 * PlayerLeagueActions.tsx): "Add to Trade" for any rostered player, "Find
 * trades" for the user's own, "Build an offer" (first, one primary button) for
 * a player on ANOTHER team, and "Add to GM Targets" (☆/★) for players not
 * on the user's roster. Roster membership comes from the same
 * useRosterOwnership hook Player Detail uses; until it answers only nothing
 * shows, never a guess. `onNavigate` lets the sheet close itself first.
 */
export default function PlayerLeagueActions({
  player,
  leagueId,
  leagueName,
  onNavigate,
  hideAddToTrade = false,
}: {
  player: RankedPlayer;
  leagueId: string;
  leagueName: string;
  onNavigate: () => void;
  /** Quick view opened inside the Trade Analyzer itself. */
  hideAddToTrade?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const ownership = useRosterOwnership(leagueId);
  const shortcuts = tradeShortcutsFor(player.player_id, ownership);
  const showAddToTrade = shortcuts.canAddToTrade && !hideAddToTrade;
  const showBuildOffer = !hideAddToTrade && canBuildOffer(player.player_id, ownership);
  const onMyRoster = ownership?.myPlayerIds.has(player.player_id) ?? null;
  const [watching, setWatching] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (onMyRoster !== false) {
      setWatching(null);
      return;
    }
    let cancelled = false;
    api
      .getGmTargets(leagueId)
      .then((result) => {
        if (!cancelled) setWatching(result.targets.some((t) => t.player_id === player.player_id));
      })
      .catch(() => {
        if (!cancelled) setWatching(null);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, player.player_id, onMyRoster]);

  const goTrades = (initialTab: 'make' | 'search') => {
    onNavigate();
    if (navigationRef.isReady()) {
      navigationRef.navigate('Trades', { leagueId, leagueName, initialTab, tradePlayer: player });
    }
  };

  const toggleWatch = async () => {
    if (watching === null || busy) return;
    setBusy(true);
    try {
      if (watching) {
        await api.removeGmTarget(leagueId, player.player_id);
        setWatching(false);
      } else {
        const result = await api.addGmTarget(leagueId, player.player_id, 'player_quick_view');
        if (result.ok) setWatching(true);
        else if (result.reason === 'at_cap') {
          Alert.alert(
            'GM Targets is full',
            `You've hit the cap for this league (${result.cap ?? 'limit reached'}). Remove a target before adding another.`,
          );
        } else Alert.alert('Could not update GM Targets', 'Please try again in a moment.');
      }
    } catch {
      Alert.alert('Could not update GM Targets', 'Please try again in a moment.');
    } finally {
      setBusy(false);
    }
  };

  const goBuildOffer = () => {
    onNavigate();
    if (navigationRef.isReady()) {
      navigationRef.navigate('TradeOffer', { leagueId, leagueName, playerId: player.player_id });
    }
  };

  if (!showBuildOffer && !showAddToTrade && !shortcuts.canFindTrades && watching === null) return null;
  return (
    <View style={styles.row}>
      {showBuildOffer ? (
        <TouchableOpacity
          style={styles.chip}
          onPress={goBuildOffer}
          accessibilityRole="button"
          accessibilityLabel={`Build an offer for ${player.name ?? 'this player'}`}
        >
          <Ionicons name="hammer-outline" size={14} color={colors.accent} />
          <AppText style={styles.chipText}>Build an offer</AppText>
        </TouchableOpacity>
      ) : null}
      {showAddToTrade ? (
        <TouchableOpacity
          style={styles.chip}
          onPress={() => goTrades('make')}
          accessibilityRole="button"
          accessibilityLabel={`Add ${player.name ?? 'this player'} to a trade`}
        >
          <Ionicons name="swap-horizontal-outline" size={14} color={colors.accent} />
          <AppText style={styles.chipText}>Add to Trade</AppText>
        </TouchableOpacity>
      ) : null}
      {shortcuts.canFindTrades ? (
        <TouchableOpacity
          style={styles.chip}
          onPress={() => goTrades('search')}
          accessibilityRole="button"
          accessibilityLabel={`Find trades for ${player.name ?? 'this player'}`}
        >
          <Ionicons name="search-outline" size={14} color={colors.accent} />
          <AppText style={styles.chipText}>Find trades</AppText>
        </TouchableOpacity>
      ) : null}
      {watching !== null ? (
        <TouchableOpacity
          style={[styles.chip, watching && styles.chipActive]}
          onPress={toggleWatch}
          disabled={busy}
          accessibilityRole="button"
        >
          <AppText style={styles.chipText}>{watching ? '★ Watching' : '☆ Add to GM Targets'}</AppText>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    // Outlined accent pill with a soft fill: web's .pqv-action-link--primary.
    chip: {
      // Two equal columns that fill the sheet gutters (one shared grid with
      // the profile/waivers buttons below), content centered in each cell.
      flexBasis: '47%',
      flexGrow: 1,
      justifyContent: 'center',
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.xs,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.xs + 2,
      minHeight: 44,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.accentMuted,
      backgroundColor: colors.glassInset,
    },
    chipActive: { borderColor: colors.accent },
    chipText: { fontSize: 13, fontWeight: '700', color: colors.accent },
  });
}
