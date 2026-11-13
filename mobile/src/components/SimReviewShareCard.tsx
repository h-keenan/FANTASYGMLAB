import React, { forwardRef } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import ShareCardChrome, { ShareGlass } from './ShareCardChrome';
import type { ReviewShareModel, ReviewTone } from '../lib/simReview';
import { colors, radii, spacing } from '../theme';

export const SIM_REVIEW_CARD_HEIGHT = 560;

/** Fixed dark palette: a captured share PNG never follows the viewer's theme. */
function toneColor(tone: ReviewTone): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    default: return colors.textSecondary;
  }
}

/** Season in Review share card; the same ReviewShareModel feeds web's Satori card. */
const SimReviewShareCard = forwardRef<View, { model: ReviewShareModel }>(({ model }, ref) => {
  const gradeColor = toneColor(model.gradeTone);
  return (
    <ShareCardChrome ref={ref} kind={model.title} height={SIM_REVIEW_CARD_HEIGHT}>
      <ShareGlass style={[styles.hero, { borderColor: gradeColor }]}>
        <AppText style={[styles.grade, { color: gradeColor }]}>{model.letter || '-'}</AppText>
        <View style={styles.heroText}>
          <AppText style={styles.headline} numberOfLines={2}>{model.headline}</AppText>
          {model.subline ? <AppText style={styles.subline} numberOfLines={2}>{model.subline}</AppText> : null}
        </View>
      </ShareGlass>
      {model.highlights.map((h, i) => (
        <ShareGlass key={i} style={[styles.row, { borderLeftColor: toneColor(h.tone) }]}>
          <View style={styles.rowText}>
            <AppText style={[styles.kind, { color: toneColor(h.tone) }]}>{h.label}</AppText>
            <AppText style={styles.rowTitle} numberOfLines={1}>{h.text}</AppText>
          </View>
          {h.delta ? <AppText style={[styles.delta, { color: toneColor(h.tone) }]}>{h.delta}</AppText> : null}
        </ShareGlass>
      ))}
      <View style={styles.stats}>
        {model.stats.map((s, i) => (
          <ShareGlass key={i} style={styles.stat}>
            <AppText style={styles.kind}>{s.label}</AppText>
            <AppText style={styles.statValue}>{s.value}</AppText>
          </ShareGlass>
        ))}
      </View>
    </ShareCardChrome>
  );
});
SimReviewShareCard.displayName = 'SimReviewShareCard';
export default SimReviewShareCard;

const styles = StyleSheet.create({
  hero: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, padding: spacing.md, borderWidth: 1 },
  grade: { fontSize: 72, lineHeight: 78, fontWeight: '900' },
  heroText: { flex: 1, minWidth: 0, gap: 2 },
  headline: { fontSize: 18, fontWeight: '900', color: colors.textPrimary },
  subline: { fontSize: 12, color: colors.textSecondary },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, padding: spacing.sm, borderLeftWidth: 4, borderRadius: radii.md },
  rowText: { flex: 1, minWidth: 0 },
  kind: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
  rowTitle: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
  delta: { fontSize: 16, fontWeight: '900' },
  stats: { flexDirection: 'row', gap: spacing.xs },
  stat: { flex: 1, padding: spacing.sm },
  statValue: { fontSize: 16, fontWeight: '900', color: colors.textPrimary },
});
