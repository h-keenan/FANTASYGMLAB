import React, { useMemo } from 'react';
import { StyleProp, StyleSheet, TouchableOpacity, View, ViewStyle } from 'react-native';

import AppText from './AppText';
import OverallRatingBadge from './OverallRatingBadge';
import PlayerAvatar from './PlayerAvatar';
import PlayerNameText from './PlayerNameText';
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
  /** 0-99 "OVR" badge rendered alongside the tier/position chips (see
   * OverallRatingBadge) — the colored avatar ring only conveys relative
   * tier, not how two similarly-tiered players actually compare, so this
   * is the number that answers that (coridian_, Trade Hub card feedback:
   * "I think that they should have the overall and then their prestige,
   * which is already on their colored [ring]"). Omit (or pass null) for
   * contexts that already show OVR elsewhere, e.g. a value column next to
   * this row — see TeamRosterScreen/MyTeamScreen's CompactRosterRow, which
   * render OverallRatingBadge outside this component instead. Renders
   * nothing for null/undefined, same as OverallRatingBadge itself. */
  overallRating?: number | null;
  /** This player's league-wide/pool "RB1"-style position rank (never a
   * team-roster-relative rank — see lib/positionRankPrestige.ts) — pass the
   * same value a row already renders as its own separate rank pill, if any.
   * Forwarded straight to OverallRatingBadge's `positionRank`, so a top-5
   * rank renders the crowned, prestige-tinted OVR badge instead of the
   * plain percentile-tinted one. Ignored when `overallRating` is absent. */
  positionRank?: number | null;
  /** Lineup slot label (QB/RB/FLEX/...) shown as a small chip on the left —
   * omit for contexts with no lineup slot (e.g. a plain roster list). When
   * `slot` is a single-position label that exactly matches `position`
   * (case-insensitively — e.g. slot "QB" + position "QB"), this component
   * suppresses the slot chip itself rather than showing the same text twice
   * next to the colored PositionBadge. Multi-position slots (FLEX,
   * SUPER_FLEX, WR/RB, ...) never equal a single real position, so they
   * always render both chips — that combination is the actually-informative
   * one and must never be collapsed. */
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
  /** Small informational pill for Sleeper's GLOBAL trending-add signal
   * (cross-league, last-24h add velocity across all of Sleeper — see
   * WaiverRecommendationCard's `waiverTrendingAddLabel` helper and api.ts's
   * WaiverPlayer.sleeper_trending_add doc comment). Pass the pre-built
   * label text (e.g. "Trending on Sleeper +482") or null/undefined to
   * render nothing — this component never fabricates the label itself, and
   * never implies a league-specific signal. */
  trendingAddLabel?: string | null;
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
  /** A smaller, muted SECOND figure under the main trailing block — e.g. a
   * per-game projection ("Proj 14.2") sitting under a real live/actual
   * score. Deliberately smaller and quieter than `trailingValue` so it
   * never competes with the row's one dominant metric (Magna Carta's "one
   * dominant module/metric" rule) — always a supporting number, never a
   * second equally-weighted one. Ignored when `trailingValue` is absent
   * (there is nothing to sit "under" otherwise). */
  secondaryTrailingValue?: string | null;
  /** One short line under `secondaryTrailingValue`, e.g. "med conf".
   * Ignored when `secondaryTrailingValue` is absent. */
  secondaryTrailingCaption?: string | null;
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
  overallRating,
  positionRank,
  slot,
  opportunityLabel,
  contextLine,
  injuryLabel,
  ruledOut,
  injuryTone = 'risk',
  trendingAddLabel,
  trailingValue,
  trailingCaption,
  secondaryTrailingValue,
  secondaryTrailingCaption,
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

  // A single-position lineup slot (QB/RB/WR/TE/K/DEF/...) renders the exact
  // same text as PositionBadge two inches to its right — pure duplication
  // (coridian_, My Team Overview screenshot, 2026-09-26). A multi-position
  // slot (FLEX, SUPER_FLEX, WR/RB, ...) never collides with a real position
  // string, so this simple equality check naturally leaves those — the only
  // combination that's actually informative — untouched without needing an
  // explicit slot-name whitelist. The colored PositionBadge wins the
  // dedup (it's the consistently-styled, app-wide identity chip); the slot
  // chip is the one suppressed.
  const slotRedundant =
    !!slot && !!position && slot.trim().toUpperCase() === position.trim().toUpperCase();

  return (
    <TouchableOpacity
      style={[styles.row, showDivider && styles.divider, style]}
      onPress={onPress}
      activeOpacity={onPress ? 0.7 : 1}
      disabled={!onPress}
    >
      {slot && !slotRedundant ? (
        <View style={styles.slotBadge}>
          <AppText style={styles.slotText} numberOfLines={1}>
            {slot}
          </AppText>
        </View>
      ) : null}
      <PlayerAvatar playerId={playerId} size={38} tier={tier} style={styles.avatar} />
      <View style={styles.body}>
        <View style={styles.nameRow}>
          {/* PlayerNameText (not a plain numberOfLines AppText) so a name
           * that doesn't fit degrades to "F. Lastname" instead of a
           * mid-word ellipsis cut — coridian_, "Jauan Jenni…" on Trade Hub's
           * exchange columns, 2026-09-27. This is the one shared row used
           * across My Team/Waivers/Trade Hub/Matchup/etc., so the fix here
           * covers every consumer at once. */}
          <PlayerNameText name={name ?? 'Unknown player'} style={styles.name} />
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
          {trendingAddLabel ? (
            <View style={styles.trendingPill}>
              <AppText style={styles.trendingPillText} numberOfLines={1}>
                {trendingAddLabel}
              </AppText>
            </View>
          ) : null}
          {/* Last in the meta row, per UI_HIERARCHY_DIRECTIVE.md §11: OVR is
           * a supporting metric, never ahead of identity/position/team/tier. */}
          <OverallRatingBadge rating={overallRating} positionRank={positionRank} />
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
          {secondaryTrailingValue ? (
            <View style={styles.secondaryTrailingRow}>
              <AppText style={styles.secondaryTrailingValue} numberOfLines={1}>
                {secondaryTrailingValue}
              </AppText>
              {secondaryTrailingCaption ? (
                <AppText style={styles.secondaryTrailingCaption} numberOfLines={1}>
                  {' '}
                  {secondaryTrailingCaption}
                </AppText>
              ) : null}
            </View>
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
    // Same muted-fill/bright-text pairing as the "CURRENT" nav badge
    // (colors.accentMuted/accent) — a neutral, purely informational tone,
    // distinct from the injury pill's risk/watch colors and from
    // TierBadge/OverallRatingBadge's own prestige colors.
    trendingPill: {
      backgroundColor: colors.accentMuted,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.xs + 2,
      paddingVertical: 1,
    },
    trendingPillText: { fontSize: 9.5, fontWeight: '700', color: colors.accent },
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
    // Deliberately smaller/quieter than trailingValue/trailingCaption above
    // — a supporting secondary figure (e.g. a projection next to a real
    // score), never a second equally-weighted metric on the row.
    secondaryTrailingRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: 2 },
    secondaryTrailingValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
    secondaryTrailingCaption: { fontSize: 9, color: colors.textTertiary },
  });
}
