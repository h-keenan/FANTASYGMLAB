import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import CompactPlayerModule from './CompactPlayerModule';
import NewBadge from './NewBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * Player-aware sibling of InsightRow (see that component's docstring for the
 * shared "short analytical conclusion" row shape) — same icon/label/action-
 * chip chrome, but the headline/detail slot is replaced with
 * CompactPlayerModule so a Watch/Waiver Opportunity/League Movement item
 * that's actually about one player shows a real identity (portrait,
 * position, tier, value) instead of a bare name baked into a headline
 * string.
 *
 * Deliberately a separate component rather than a change to InsightRow
 * itself: InsightRow is shared with non-player rows (e.g. My Team's
 * Strengths/Risks), so its plain string headline/detail contract stays
 * untouched. A caller with a route_player_id renders this instead; every
 * other InsightRow caller is unaffected.
 */
export default function PlayerInsightRow({
  icon,
  color,
  label,
  headline,
  isNew,
  actionLabel,
  onActionPress,
  onPress,
  last,
  playerId,
  playerName,
  position,
  team,
  tier,
  value,
  valueLabel,
  detail,
}: {
  icon: IconName;
  color: string;
  label?: string | null;
  /** The tile's own headline text, shown above the player module — omit
   * (pass null) when the headline is nothing more than the player's own
   * name, since CompactPlayerModule already shows that identity and
   * repeating it as a text line would just duplicate it. */
  headline?: string | null;
  isNew?: boolean;
  actionLabel?: string | null;
  onActionPress?: () => void;
  /** Row-level tap — navigates into the referenced player. */
  onPress?: () => void;
  last?: boolean;
  playerId: string | null | undefined;
  playerName: string | null | undefined;
  position?: string | null;
  team?: string | null;
  tier?: string | null;
  value?: number | null;
  valueLabel?: string | null;
  /** Same role as InsightRow's `detail` — the reason/note text, shown only
   * when provided. */
  detail?: string | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const Wrapper = onPress ? TouchableOpacity : View;

  return (
    <Wrapper
      style={[styles.row, !last && styles.rowDivider]}
      {...(onPress ? { onPress, activeOpacity: 0.7 } : null)}
    >
      <Ionicons name={icon} size={16} color={color} style={styles.icon} />
      <View style={styles.contentGroup}>
        {label ? (
          <View style={styles.labelRow}>
            <AppText style={[styles.label, { color }]} numberOfLines={1}>
              {label.toUpperCase()}
            </AppText>
            {isNew ? <NewBadge /> : null}
          </View>
        ) : null}
        {headline ? (
          <AppText style={styles.headline} numberOfLines={2}>
            {headline}
          </AppText>
        ) : null}
        <CompactPlayerModule
          playerId={playerId}
          name={playerName}
          position={position}
          team={team}
          tier={tier}
          value={value}
          valueLabel={valueLabel}
          contextLine={detail}
        />
      </View>
      {actionLabel && onActionPress ? (
        <TouchableOpacity style={styles.actionChip} onPress={onActionPress} hitSlop={6}>
          <AppText style={styles.actionChipText}>{actionLabel.toUpperCase()}</AppText>
        </TouchableOpacity>
      ) : onPress ? (
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      ) : null}
    </Wrapper>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: spacing.md,
      gap: spacing.sm,
    },
    rowDivider: {
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.hairline,
    },
    icon: { alignSelf: 'flex-start', marginTop: 2 },
    contentGroup: { flex: 1, gap: 3 },
    labelRow: { flexDirection: 'row', alignItems: 'center' },
    label: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
    headline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    actionChip: {
      borderWidth: 1,
      borderColor: colors.accent,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.xs,
      alignSelf: 'center',
    },
    actionChipText: { fontSize: 10, fontWeight: '700', color: colors.accent, letterSpacing: 0.3 },
  });
}
