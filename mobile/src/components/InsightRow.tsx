import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import NewBadge from './NewBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * The shared "short analytical conclusion" row — UI_MAGNA_CARTA.md §28's
 * Insight Row ("icon, insight headline, optional supporting context,
 * optional chevron... do not put every insight into a giant alert card").
 *
 * Introduced for the Dashboard V2 rebuild: Watch/Waiver Opportunity/League
 * Movement items previously each rendered as their own full AnimatedCard —
 * identical visual weight to the Top Priority hero card, which is exactly
 * the "too many cards feel visually similar" problem coridian_ flagged.
 * Callers now group several InsightRows inside one AnimatedCard surface
 * with internal dividers (§12) instead of card-per-item.
 *
 * Two independent tap targets, same nesting AlertsScreen's own AlertRow /
 * the pre-rebuild BriefingCard already relied on: the row itself (drill-down
 * — e.g. into the affected player) and an optional compact trailing action
 * button (a real destination, e.g. "Open Waivers"). Genuinely reusable
 * beyond Dashboard — AlertsScreen's local AlertRow follows the same
 * icon+label+headline+detail shape and could migrate to this component in a
 * later pass.
 */
export default function InsightRow({
  icon,
  color,
  label,
  headline,
  detail,
  isNew,
  actionLabel,
  onActionPress,
  onPress,
  last,
}: {
  icon: IconName;
  /** Semantic accent for the icon/label — never a one-off hue per screen. */
  color: string;
  /** Eyebrow category, e.g. "WATCH" / "WAIVER OPPORTUNITY". */
  label: string;
  headline: string;
  /** Optional supporting explanation, shown only when provided. */
  detail?: string | null;
  isNew?: boolean;
  /** Compact trailing CTA text, e.g. "OPEN WAIVERS". Rendered as its own
   * tap target, independent of `onPress` — mirrors the pre-rebuild
   * DestinationButton's own separate press handler. */
  actionLabel?: string | null;
  onActionPress?: () => void;
  /** Row-level tap (e.g. drill into the referenced player). Renders a
   * trailing chevron when there's no `actionLabel` to show instead. */
  onPress?: () => void;
  /** Suppresses the bottom divider — pass for the final row in a group. */
  last?: boolean;
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
      <View style={styles.textGroup}>
        <View style={styles.labelRow}>
          <AppText style={[styles.label, { color }]} numberOfLines={1}>
            {label.toUpperCase()}
          </AppText>
          {isNew ? <NewBadge /> : null}
        </View>
        <AppText style={styles.headline} numberOfLines={2}>
          {headline}
        </AppText>
        {detail ? (
          <AppText style={styles.detail} numberOfLines={2}>
            {detail}
          </AppText>
        ) : null}
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
      alignItems: 'flex-start',
      paddingVertical: spacing.md,
      gap: spacing.sm,
    },
    rowDivider: {
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.hairline,
    },
    icon: { marginTop: 2 },
    textGroup: { flex: 1, gap: 2 },
    labelRow: { flexDirection: 'row', alignItems: 'center' },
    label: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
    headline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    detail: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
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
