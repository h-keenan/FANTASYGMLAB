import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

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
  onPress?: () => void;
  /** Renders a hairline divider under the row — set false on the last row
   * of a group so the group's own bottom edge stays clean. */
  showDivider?: boolean;
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
 * pick row (and Dashboard/Draft Center/Trade Analyzer each still have their
 * own separate inline versions — not migrated to this component in the
 * same change). Meant to sit inside a shared card/surface as one of several
 * rows separated by `showDivider`, not individually bordered — same
 * contract as PlayerIdentityRow.
 */
export default function DraftPickAssetRow({
  round,
  label,
  projectedRange,
  pickTier,
  contextLine,
  onPress,
  showDivider = false,
}: DraftPickAssetRowProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const metaLine = [projectedRange, pickTier].filter(Boolean).join(' · ');

  return (
    <TouchableOpacity
      style={[styles.row, showDivider && styles.divider]}
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
  });
}
