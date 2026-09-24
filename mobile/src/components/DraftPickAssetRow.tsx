import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, TouchableOpacity, View, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export interface DraftPickAssetRowProps {
  /** Presence-only — used by callers to key/gate navigation, never rendered. */
  pickId?: string | null;
  /** Round number for the compact badge (e.g. 3 -> "R3"); falls back to a
   * generic "PICK" badge when absent (e.g. a pick whose round isn't known
   * yet). */
  round?: number | null;
  /** Primary line, e.g. "2026 Round 3" — the pick's own display label,
   * never derived/formatted here. */
  label?: string | null;
  /** Secondary descriptor, e.g. "Late 3rd" (projected slot within the
   * round). */
  projectedRange?: string | null;
  /** Optional tertiary descriptor, e.g. "Good"/"Elite" pick-quality tier —
   * joined onto the same meta line as `projectedRange` when both exist. */
  pickTier?: string | null;
  /** One extra short line below the meta row (e.g. current owner's team
   * name) — kept to a single line by the caller, same contract as
   * PlayerIdentityRow's `contextLine`. */
  contextLine?: string | null;
  /** Optional bold value shown at the trailing edge, e.g. an estimated
   * value score ("82"). Right-aligned, same weight class as
   * PlayerIdentityRow's metric emphasis. Omit for contexts with no
   * standalone value to show (e.g. Trade Hub's exchange rows, where value
   * lives in the trade's own hero instead). */
  trailingValue?: string | null;
  /** One short line under `trailingValue`, e.g. "74% conf". Ignored when
   * `trailingValue` is absent. */
  trailingCaption?: string | null;
  /** Renders a chevron-forward affordance after the trailing value block —
   * opt-in so existing non-navigating callers are unaffected. Defaults to
   * false. */
  showChevron?: boolean;
  onPress?: () => void;
  /** Renders a hairline divider under the row — set false on the last row
   * of a group so the group's own bottom edge stays clean. */
  showDivider?: boolean;
  /** Optional style override for the row container — e.g. to give it `flex:
   * 1` when it shares a horizontal row with a sibling action button (see
   * Trade Analyzer's pick search results, which pair this row with a
   * separate "view pick detail" affordance). */
  style?: StyleProp<ViewStyle>;
}

/**
 * Generic, reusable draft-pick asset row — the pick-side counterpart to
 * PlayerIdentityRow. Draft picks are not players (no position/tier/injury
 * identity), so they get their own compact treatment: a small amber "R{n}"
 * badge (amber = draft-capital/opportunity, the app's fixed semantic color
 * for this asset class) instead of a player portrait, a bold primary label,
 * and a one-line projected-slot / pick-quality meta line.
 *
 * Built for the Trade Hub redesign, which previously had its own inline
 * pick row (and Dashboard/Trade Analyzer still have their own separate
 * inline versions — not migrated to this component in the same change).
 * Meant to sit inside a shared card/surface as one of several rows
 * separated by `showDivider`, not individually bordered — same contract as
 * PlayerIdentityRow.
 *
 * Draft Center's Pick Values list also renders through this row (with
 * `trailingValue`/`trailingCaption`/`showChevron`, which Trade Hub's
 * exchange rows leave unset) — see DraftCenterScreen's `pickSeasons`
 * rendering.
 */
export default function DraftPickAssetRow({
  round,
  label,
  projectedRange,
  pickTier,
  contextLine,
  trailingValue,
  trailingCaption,
  showChevron = false,
  onPress,
  showDivider = false,
  style,
}: DraftPickAssetRowProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const metaLine = [projectedRange, pickTier].filter(Boolean).join(' · ');

  return (
    <TouchableOpacity
      style={[styles.row, showDivider && styles.divider, style]}
      onPress={onPress}
      activeOpacity={onPress ? 0.7 : 1}
      disabled={!onPress}
    >
      <View style={styles.badge}>
        <AppText style={styles.badgeText} numberOfLines={1}>
          {round ? `R${round}` : 'PICK'}
        </AppText>
      </View>
      <View style={styles.body}>
        <AppText style={styles.label} numberOfLines={1}>
          {label || 'Draft pick'}
        </AppText>
        {metaLine ? (
          <AppText style={styles.meta} numberOfLines={1}>
            {metaLine}
          </AppText>
        ) : null}
        {contextLine ? (
          <AppText style={styles.context} numberOfLines={1}>
            {contextLine}
          </AppText>
        ) : null}
      </View>
      {trailingValue ? (
        <View style={styles.trailingBlock}>
          <AppText style={styles.trailingValue} numberOfLines={1}>
            {trailingValue}
          </AppText>
          {trailingCaption ? (
            <AppText style={styles.trailingCaption} numberOfLines={1}>
              {trailingCaption}
            </AppText>
          ) : null}
        </View>
      ) : null}
      {showChevron ? (
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} style={styles.chevron} />
      ) : null}
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.sm + 2 },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    badge: {
      width: 38,
      height: 38,
      borderRadius: 19,
      backgroundColor: colors.premiumMuted,
      borderWidth: 1.5,
      borderColor: colors.premium,
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: spacing.sm,
    },
    badgeText: { fontSize: 11, fontWeight: '800', color: colors.premium },
    body: { flex: 1, gap: 1 },
    label: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 11, color: colors.textSecondary },
    context: { fontSize: 11, color: colors.textTertiary },
    trailingBlock: { alignItems: 'flex-end', marginLeft: spacing.sm },
    trailingValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    trailingCaption: { fontSize: 10, color: colors.textTertiary, marginTop: 1 },
    chevron: { marginLeft: spacing.xs },
  });
}
