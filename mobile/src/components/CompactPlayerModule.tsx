import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, TouchableOpacity, View, ViewStyle } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

export interface CompactPlayerModuleProps {
  playerId: string | null | undefined;
  name: string | null | undefined;
  position?: string | null;
  team?: string | null;
  /** Raw stored tier (e.g. "Elite", "Core Starter") — same string
   * PlayerIdentityRow/PlayerAvatar take, drives the avatar's prestige ring.
   * Omit or pass null/empty when this row's underlying data has no tier on
   * file; the avatar just renders a neutral ring rather than fabricating
   * one (matches this codebase's "never fabricate" pattern). */
  tier?: string | null;
  /** One trailing value/overall number (e.g. a value score) — omitted
   * entirely when null/undefined rather than showing a placeholder. */
  value?: number | null;
  /** Short caption under `value`, e.g. "VALUE". Ignored when `value` is
   * absent. */
  valueLabel?: string | null;
  /** Optional single line of supporting context under the name — e.g. an
   * injury status/relevance read for an injury-impact card. Kept to one
   * line by the caller. */
  contextLine?: string | null;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
}

/**
 * The compact player identity module for dense list/summary contexts —
 * Dashboard's Needs Attention / Opportunities rows and injury-impact
 * bullets, where a full PlayerIdentityRow is too heavy but a bare name
 * string throws away the player's real identity (portrait, position, tier).
 *
 * Same visual family as PlayerIdentityRow (UI_MAGNA_CARTA.md §"Shared
 * player identity ... variants: compact row, standard row, hero") — reuses
 * the exact same PlayerAvatar/PositionBadge atoms rather than inventing a
 * second player-identity look, just at a tighter footprint (smaller avatar,
 * no slot chip, no injury pill, one trailing number instead of a full
 * trailing block).
 *
 * Tappable when `onPress` is provided — callers should navigate to
 * PlayerDetail the same way every other player tap does.
 */
export default function CompactPlayerModule({
  playerId,
  name,
  position,
  team,
  tier,
  value,
  valueLabel,
  contextLine,
  onPress,
  style,
}: CompactPlayerModuleProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const Wrapper = onPress ? TouchableOpacity : View;
  const hasValue = value != null && Number.isFinite(value);

  return (
    <Wrapper
      style={[styles.row, style]}
      {...(onPress ? { onPress, activeOpacity: 0.7 } : null)}
    >
      <PlayerAvatar playerId={playerId} size={34} tier={tier} style={styles.avatar} />
      <View style={styles.body}>
        <AppText style={styles.name} numberOfLines={1}>
          {name ?? 'Unknown player'}
        </AppText>
        <View style={styles.metaRow}>
          <PositionBadge position={position} size="sm" />
          {team ? (
            <AppText style={styles.team} numberOfLines={1}>
              {team}
            </AppText>
          ) : null}
        </View>
        {contextLine ? (
          <AppText style={styles.context} numberOfLines={1}>
            {contextLine}
          </AppText>
        ) : null}
      </View>
      {hasValue ? (
        <View style={styles.trailingBlock}>
          <AppText style={styles.trailingValue} numberOfLines={1}>
            {Math.round(value as number)}
          </AppText>
          {valueLabel ? (
            <AppText style={styles.trailingCaption} numberOfLines={1}>
              {valueLabel}
            </AppText>
          ) : null}
        </View>
      ) : null}
    </Wrapper>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    avatar: {},
    body: { flex: 1, gap: 1 },
    name: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    team: { fontSize: 10.5, color: colors.textSecondary },
    context: { fontSize: 11, color: colors.textTertiary, marginTop: 1 },
    trailingBlock: { alignItems: 'flex-end', marginLeft: spacing.sm },
    trailingValue: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    trailingCaption: { fontSize: 9, color: colors.textTertiary, marginTop: 1 },
  });
}
