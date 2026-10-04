import React from 'react';
import { StyleSheet, View } from 'react-native';

import OverallRatingBadge from './OverallRatingBadge';
import type { SubRating } from '../lib/subRatings';
import { spacing } from '../theme';

/**
 * Compact row of position-percentile sub-rating chips — "MKT 91 · OPP 84 ·
 * SCR 62 · ROLE 73 · DUR 58" — the Model tab's Market/Opportunity/
 * Scarcity/Role/Durability breakdown. Each chip is literally
 * OverallRatingBadge with its own trailing label instead of "OVR", so every
 * number here is tinted by the exact same percentileColor ramp (and sits on
 * the exact same 0-99 curve) as the headline OVR ring — never a second,
 * drifting color/scale treatment.
 *
 * Also reused verbatim on PlayerShareCard as the share card's "headline
 * attributes" row (see lib/subRatings.playerSubRatings, which builds this
 * same array for both surfaces) — a Madden Ultimate Team card's
 * portrait + OVR + a handful of color-coded sub-attributes.
 *
 * Entries whose rating is null/undefined are skipped entirely
 * (OverallRatingBadge's own "too thin a pool to rank against" contract)
 * rather than rendering an empty/placeholder chip; the whole row renders
 * nothing if every entry is unrankable.
 */
export default function SubRatingRow({
  ratings,
  size = 'sm',
}: {
  ratings: SubRating[];
  size?: 'sm' | 'md';
}) {
  const visible = ratings.filter(
    (item) => item.rating !== null && item.rating !== undefined && Number.isFinite(item.rating),
  );
  if (!visible.length) return null;
  return (
    <View style={styles.row}>
      {visible.map((item) => (
        <OverallRatingBadge key={item.label} rating={item.rating} label={item.label} size={size} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
});
