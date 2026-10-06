import React from 'react';
import { StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { percentileColor } from '../lib/percentile';
import { positionRankPrestige } from '../lib/positionRankPrestige';
import { radii, spacing } from '../theme';

/**
 * Small "94 OVR" pill — the 0-99 headline rating (see
 * modules.player_quick_view._overall_rating_from_percentile) shown as a
 * secondary badge next to a row's primary raw value_score, never in place
 * of it. Tinted by the rating itself via the shared red->gold->green
 * percentile ramp (OVR is already a 0-99 scale, so it's fed straight into
 * `percentileColor` — same function Player Detail's OVR ring uses) instead
 * of one flat neutral gray: coridian_ flagged the gray pills as looking
 * bad and asked for low-OVR-redder/high-OVR-greener (screenshot,
 * 2026-09-23).
 *
 * Renders nothing for `null`/`undefined` — the same "too thin a pool to
 * rank against" contract every overall_rating field already carries, so a
 * screen never has to gate on presence itself.
 *
 * `positionRank`: pass the same league-wide/pool "RB1"-style position rank
 * a row already renders as its own separate pill (never a team-roster-
 * relative rank — this app has none). coridian_ flagged that "RB1"/"RB2"
 * reads as ambiguous between "best RB in the league" and "this is my own
 * team's RB1/RB2" (Discord). For a top-5 rank, this badge swaps its usual
 * percentile tint for a crowned, gold/silver/bronze prestige fill (see
 * lib/positionRankPrestige.ts — the same hues AwardsStrip's award tiers
 * already use) so the module itself signals "this number reflects a global
 * rank," not just an ordinary high rating. Every rank outside the top 5 (or
 * omitted entirely) renders exactly as before.
 *
 * `label`: the trailing tag after the number — defaults to "OVR" (the
 * headline rating) but any other 0-99-scale rating sharing the same curve
 * and percentileColor tint can reuse this exact pill with its own short tag
 * (e.g. "MKT", "DUR") — see SubRatingRow, the Model tab's sub-rating chip
 * row, which is the first other caller.
 */
export default function OverallRatingBadge({
  rating,
  size = 'sm',
  positionRank,
  label = 'OVR',
}: {
  rating: number | null | undefined;
  size?: 'sm' | 'md';
  positionRank?: number | null;
  label?: string;
}) {
  const { colors, isDark } = useThemeMode();
  if (rating === null || rating === undefined || !Number.isFinite(rating)) return null;
  const prestige = positionRankPrestige(positionRank, isDark);
  const tint = prestige.color ?? percentileColor(rating, colors);
  return (
    <View
      style={[
        styles.badge,
        size === 'md' && styles.badgeMd,
        prestige.tier && styles.badgeCrowned,
        { backgroundColor: `${tint}26`, borderColor: `${tint}70` },
      ]}
    >
      {prestige.tier ? (
        <MaterialCommunityIcons
          name="crown"
          size={size === 'md' ? 12 : 10}
          color={tint}
          style={styles.crown}
          accessibilityElementsHidden
        />
      ) : null}
      <AppText
        style={[styles.text, size === 'md' && styles.textMd, { color: tint }]}
        numberOfLines={1}
        accessibilityLabel={prestige.tier ? `League-wide number ${positionRank} at position, ${Math.round(rating)} overall rating` : undefined}
      >
        {Math.round(rating)} {label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    // No alignSelf override: every call site places this inside a column
    // whose own alignItems (flex-end next to a right-aligned value score,
    // or center in a centered card) is what should decide the pill's
    // horizontal position — unlike PositionBadge/TierBadge, which always
    // sit inside a row and need flex-start to avoid stretching to the
    // row's full height.
    flexShrink: 0,
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  badgeMd: { paddingHorizontal: spacing.sm, paddingVertical: 3 },
  // Top-5 league-wide/pool rank only (see `prestige.tier` above) — the
  // crown icon stacks above the rating instead of sitting beside it, so a
  // prestige badge reads as a distinct little module, not just a
  // recolored version of the ordinary pill.
  badgeCrowned: { alignItems: 'center', paddingTop: 2, gap: 1 },
  crown: { marginBottom: -1 },
  text: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  textMd: { fontSize: 11 },
});
