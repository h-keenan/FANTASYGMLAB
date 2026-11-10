import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import RatingHistoryChart from './RatingHistoryChart';
import type { RatingHistoryResponse } from '../lib/api';
import { formatRatingDelta, ratingHistoryCaption } from '../lib/valueHistoryPresentation';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/** "Value history" body for Player Quick View: the real stored daily rating
 * snapshots, with the true span stated. Rendered by the sheet only when history is readable. Mirrors web's PlayerValueHistory. */
export default function PlayerValueHistory({ history }: { history: RatingHistoryResponse }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const caption = ratingHistoryCaption(history);
  if (!caption) return null;
  return (
    <View testID="player-value-history" style={styles.wrap}>
      {caption.chart ? <RatingHistoryChart points={history.points} /> : null}
      {caption.changes.length ? <AppText style={styles.changes}>{caption.changes.join(' · ')}</AppText> : null}
      <AppText style={styles.caption}>
        {caption.text}
        {history.current_rating != null ? ` Latest rating ${history.current_rating}.` : ''}
        {!caption.changes.length && caption.chart && history.change
          ? ` ${formatRatingDelta(history.change.delta)} since the first snapshot.`
          : ''}
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.xs },
    changes: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    caption: { fontSize: 12, color: colors.textTertiary },
  });
}
