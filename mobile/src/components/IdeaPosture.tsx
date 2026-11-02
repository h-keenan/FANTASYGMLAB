import React from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PostureChip from './PostureChip';
import ToneBadge from './ToneBadge';
import type { TradePosture } from '../lib/api';
import { colors, spacing } from '../theme';

export interface IdeaPostureFields {
  posture?: TradePosture | null;
  posture_label?: string;
  posture_note?: string;
  posture_alignment?: 'aligned' | 'neutral' | 'costly' | '';
}

/**
 * The team posture a trade idea was graded and ranked under: the shared
 * PostureChip, the Analyzer's honest label when the idea is a trade-off, and the
 * one-line note (modules/trade_posture.py). Mirrors web-next's IdeaPosture; used by
 * Trade Hub / Finder cards and the Dashboard trade tile.
 */
export default function IdeaPosture({ idea }: { idea: IdeaPostureFields }) {
  if (!idea.posture) return null;
  return (
    <View testID="idea-posture" style={styles.block}>
      <PostureChip posture={idea.posture} />
      {idea.posture_label ? (
        <ToneBadge label={idea.posture_label} color={colors.warning} />
      ) : idea.posture_alignment === 'aligned' ? (
        <ToneBadge label="Fits your plan" color={colors.success} />
      ) : null}
      {idea.posture_note ? <AppText style={styles.note}>{idea.posture_note}</AppText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: spacing.xs, alignItems: 'flex-start' },
  note: { fontSize: 12, lineHeight: 17, color: colors.textSecondary },
});
