import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, TouchableOpacity, View, ViewStyle } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import TierBadge from './TierBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { resolvePlayerTier } from '../lib/playerTier';
import { radii, spacing, type ThemeColors } from '../theme';

export interface PlayerIdentityRowProps {
  playerId: string | null | undefined;
  name: string | null | undefined;
  position?: string | null;
  team?: string | null;
  /** Raw stored tier (e.g. "Elite", "Core Starter") — drives both the
   * portrait ring color and the TierBadge chip, same as everywhere else in
   * the app (see lib/playerTier.ts). */
  tier?: string | null;
  /** Lineup slot label (QB/RB/FLEX/...) shown as a small chip on the left —
   * omit for contexts with no lineup slot (e.g. a plain roster list). */
  slot?: string | null;
  /** Workload/opportunity classification, e.g. "Elite Opportunity",
   * "Starter At Risk" — rendered alongside the tier in the compact label
   * row, never invented client-side. */
  opportunityLabel?: string | null;
  /** One short supporting line, e.g. "Top QB on this roster by season
   * value" — kept to a single line by the caller; this component never
   * wraps it into a paragraph. */
  contextLine?: string | null;
  /** Injury tag to render — '' / null / undefined means healthy, so no pill
   * renders at all. */
  injuryLabel?: string | null;
  /** True only for a confirmed-unavailable starter kept in the lineup
   * because nothing else was available for the slot — renders as a solid
   * (not translucent) pill so it reads as more urgent than an ordinary
   * "Questionable" tag. */
  ruledOut?: boolean;
  /** Color family for the injury pill when not `ruledOut`: 'risk' (red,
   * default — matches every existing caller) for a genuine
   * risk/out-caliber status, or 'watch' (amber) for a lower-severity flag
   * like "Questionable" that shouldn't read as urgently as "Out"/"IR".
   * `ruledOut` always wins and renders solid red regardless of tone, since
   * that state is unconditionally the most severe. Added for Waivers,
   * which previously drew this same risk/watch distinction with a
   * screen-local color helper — kept optional so Matchup/Trade Hub/etc.
   * are unaffected. */
  injuryTone?: 'risk' | 'watch';
  /** Optional bold value shown at the trailing edge, e.g. a value score
   * ("82") — same trailing-block contract as DraftPickAssetRow's
   * `trailingValue`, so a player row and a pick row can sit in the same
   * search/browse list with matching right-aligned emphasis. Omit for
   * contexts that already show value elsewhere (e.g. Trade Hub's exchange
   * rows, where value lives in the trade's own hero). */
  trailingValue?: string | null;
  /** One short line under `trailingValue`, e.g. "82% conf". Ignored when
   * `trailingValue` is absent. */
  trailingCaption?: string | null;
  onPress?: () => void;
  /** Renders a hairline divider under the row — set false on the last row
   * of a group so the group's own bottom edge stays clean. */
  showDivider?: boolean;
  /** Optional style override for the row container — e.g. to give it `flex:
   * 1` when it shares a horizontal row with a sibling action button. */
  style?: StyleProp<ViewStyle>;
}

/**
 * Generic, reusable player identity row: lineup slot, portrait, name,
 * position/team/tier identity, an optional opportunity classification +
 * one-line context, and a highly visible injury pill when relevant.
 *
 * Built for the Matchup screen's lineup sections (coridian_'s ask for a
 * shared, configurable player row rather than a screen-specific one), but
 * intentionally has no Matchup-specific knowledge — any screen that lists
 * players in a group (Rankings, Rosters, Trades, Waivers, ...) can adopt it
 * later without a second player-row implementation. Meant to sit inside a
 * single shared card/surface as one of several rows separated by dividers,
 * not individually bordered — see MatchupScreen's StarterSection for the
 * reference usage.
 */
export default function PlayerIdentityRow({
  playerId,
  name,
  position,
  team,
  tier,
  slot,
  opportunityLabel,
  contextLine,
  injuryLabel,
  ruledOut,
  injuryTone = 'risk',
  trailingValue,
  trailingCaption,
  onPress,
  showDivider = false,
  style,
}: PlayerIdentityRowProps) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tierIdentity = tier ? resolvePlayerTier(tier, isDark) : null;
  const isWatch = injuryTone === 'watch';
  const injuryPillBg = ruledOut ? colors.danger : isWatch ? colors.premiumMuted : colors.dangerMuted;
  const injuryTextColor = ruledOut ? colors.badgeText : isWatch ? colors.premium : colors.danger;

  const labelBits: string[] = [];
  if (tierIdentity) labelBits.push(tierIdentity.shortLabel);
  if (opportunityLabel) labelBits.push(opportunityLabel.toUpperCase());

  return (
    <TouchableOpacity
      style={[styles.row, showDivider && styles.divider, style]}
      onPress={onPress}
      activeOpacity={onPress ? 0.7 : 1}
      disabled={!onPress}
    >
      {slot ? (
        <View style={styles.slotBadge}>
          <AppText style={styles.slotText} numberOfLines={1}>
            {slot}
          </AppText>
        </View>
      ) : null}
      <PlayerAvatar playerId={playerId} size={38} tier={tier} style={styles.avatar} />
      <View style={styles.body}>
        <View style={styles.nameRow}>
          <AppText style={styles.name} numberOfLines={1}>
            {name ?? 'Unknown player'}
          </AppText>
          {injuryLabel ? (
            <View style={[styles.injuryPill, { backgroundColor: injuryPillBg }]}>
              <AppText style={[styles.injuryText, { color: injuryTextColor }]} numberOfLines={1}>
                {injuryLabel}
              </AppText>
            </View>
          ) : null}
        </View>
        <View style={styles.metaRow}>
          <PositionBadge position={position} />
          <TierBadge storedTier={tier} />
          {team ? (
            <AppText style={styles.team} numberOfLines={1}>
              {team}
            </AppText>
          ) : null}
        </View>
        {labelBits.length > 0 ? (
          <AppText style={styles.label} numberOfLines={1}>
            {labelBits.join(' · ')}
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
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.sm + 2 },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    slotBadge: {
      width: 34,
      height: 22,
      borderRadius: radii.sm,
      backgroundColor: colors.badgeBackground,
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: spacing.sm,
    },
    slotText: { color: colors.badgeText, fontSize: 9, fontWeight: '700' },
    avatar: { marginRight: spacing.sm },
    body: { flex: 1, gap: 2 },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    name: { flex: 1, fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, flexWrap: 'wrap' },
    team: { fontSize: 11, color: colors.textSecondary },
    label: { fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.3 },
    context: { fontSize: 11, color: colors.textTertiary },
    // Colors (background/text) are applied inline per-row from
    // injuryTone/ruledOut — see the component body — since they vary per
    // player, not per theme, and this StyleSheet is memoized on colors
    // alone.
    // flexShrink+maxWidth (not the old flexShrink: 0) so a long label like
    // "Questionable" can't claim unbounded width and squeeze `name` down to
    // one or two letters in a narrow context (e.g. Trade Hub's two-column
    // exchange rows) — coridian_ reported a player name reading as just
    // "C." next to a Questionable pill (screenshot, 2026-09-23). The pill's
    // own text still has numberOfLines={1}, so it now ellipsizes instead.
    injuryPill: {
      flexShrink: 1,
      maxWidth: '50%',
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
    },
    injuryText: { fontSize: 10, fontWeight: '700' },
    trailingBlock: { alignItems: 'flex-end', marginLeft: spacing.sm },
    trailingValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    trailingCaption: { fontSize: 10, color: colors.textTertiary, marginTop: 1 },
  });
}
