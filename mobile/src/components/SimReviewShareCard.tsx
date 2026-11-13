import React, { forwardRef, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import ShareCardChrome, { ShareGlass } from './ShareCardChrome';
import SimCrest from './SimCrest';
import { REVIEW_ICON } from './SeasonReviewSections';
import { splitReviewGrade, type ReviewShareHighlight, type ReviewShareModel, type ReviewTone } from '../lib/simReview';
import { colors, positionColor, radii, spacing } from '../theme';

export const SIM_REVIEW_CARD_HEIGHT = 670;

const GOLD = colors.premium;
const GOLD_SOFT = '#FDE68A';
const HEADSHOT_BASE = 'https://sleepercdn.com/content/nfl/players/thumb';

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

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('');
}

/** Sleeper headshot in a position-colored ring; initials when there is no photo or it fails to load. */
function Headshot({ player, size }: { player: NonNullable<ReviewShareHighlight['player']>; size: number }) {
  const [failed, setFailed] = useState(false);
  const ring = positionColor(player.pos);
  const frame = { width: size, height: size, borderRadius: size / 2, borderColor: ring, borderWidth: 2 };
  if (player.headshotId && !failed) {
    return (
      <Image
        source={{ uri: `${HEADSHOT_BASE}/${encodeURIComponent(player.headshotId)}.jpg` }}
        style={[frame, styles.photo]}
        resizeMode="cover"
        onError={() => setFailed(true)}
        accessibilityIgnoresInvertColors
      />
    );
  }
  return (
    <View style={[frame, styles.initials, { backgroundColor: `${ring}29` }]}>
      <AppText style={[styles.initialsText, { color: ring, fontSize: size * 0.34 }]}>{initials(player.name)}</AppText>
    </View>
  );
}

/** Season in Review share card; the same ReviewShareModel feeds web's Satori card. */
const SimReviewShareCard = forwardRef<View, { model: ReviewShareModel }>(({ model }, ref) => {
  const gradeColor = toneColor(model.gradeTone);
  const champion = model.outcome === 'champion';
  const accent = champion ? GOLD : gradeColor;
  const { base, modifier } = splitReviewGrade(model.letter);
  return (
    <ShareCardChrome ref={ref} kind={model.title} height={SIM_REVIEW_CARD_HEIGHT}>
      <ShareGlass style={[styles.hero, { borderColor: champion ? GOLD : `${gradeColor}80`, borderWidth: champion ? 2 : 1, backgroundColor: champion ? `${GOLD}26` : undefined }]}>
        {model.teamName ? (
          <View style={styles.teamRow}>
            <SimCrest name={model.teamName} size={34} />
            <View style={styles.flex}>
              <AppText style={styles.kind}>Your team</AppText>
              <AppText style={styles.team} numberOfLines={1}>{model.teamName}</AppText>
            </View>
          </View>
        ) : null}
        <View style={styles.gradeRow}>
          <View style={styles.gradeBox}>
            <AppText style={[styles.grade, { color: gradeColor }]}>{base}</AppText>
            {modifier ? (
              <View style={[styles.modifier, { borderColor: gradeColor, backgroundColor: `${gradeColor}29` }]}>
                <AppText style={[styles.modifierText, { color: gradeColor }]}>{modifier === '-' ? '−' : '+'}</AppText>
              </View>
            ) : null}
          </View>
          <View style={styles.flex}>
            <View style={styles.titleRow}>
              {champion ? <Ionicons name="trophy-outline" size={20} color={GOLD} /> : null}
              <AppText style={[styles.headline, champion && { color: GOLD_SOFT }]} numberOfLines={2}>{model.headline}</AppText>
            </View>
            {model.subline ? <AppText style={styles.subline} numberOfLines={2}>{model.subline}</AppText> : null}
            {model.tags.length ? (
              <View style={styles.tags}>
                {model.tags.map((tag, i) => (
                  <View key={i} style={[styles.tag, { borderColor: `${accent}66`, backgroundColor: `${accent}1A` }]}>
                    <AppText style={styles.tagText}>{tag}</AppText>
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        </View>
      </ShareGlass>
      {model.highlights.map((h, i) => (
        <ShareGlass key={i} style={[styles.row, { borderLeftColor: toneColor(h.tone) }]}>
          {h.player ? (
            <Headshot player={h.player} size={36} />
          ) : (
            <View style={[styles.glyphDisc, { backgroundColor: `${toneColor(h.tone)}26` }]}>
              <Ionicons name={REVIEW_ICON[h.glyph]} size={18} color={toneColor(h.tone)} />
            </View>
          )}
          <View style={styles.rowText}>
            <View style={styles.labelRow}>
              <Ionicons name={REVIEW_ICON[h.glyph]} size={11} color={toneColor(h.tone)} />
              <AppText style={[styles.kind, { color: toneColor(h.tone) }]} numberOfLines={1}>{h.label}</AppText>
            </View>
            <AppText style={styles.rowTitle} numberOfLines={1}>{h.text}</AppText>
            {h.player ? (
              <AppText style={styles.meta} numberOfLines={1}>
                <AppText style={[styles.meta, { color: positionColor(h.player.pos), fontWeight: '800' }]}>{h.player.pos}</AppText>
                {h.player.team ? `  ${h.player.team}` : ''}
              </AppText>
            ) : null}
          </View>
          {h.delta ? <AppText style={[styles.delta, { color: toneColor(h.tone) }]}>{h.delta}</AppText> : null}
        </ShareGlass>
      ))}
      <View style={styles.stats}>
        {model.stats.map((s, i) => (
          <ShareGlass key={i} style={styles.stat}>
            <AppText style={styles.kind} numberOfLines={2}>{s.label}</AppText>
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
  flex: { flex: 1, minWidth: 0 },
  hero: { flexDirection: 'column', gap: spacing.sm, padding: spacing.md, borderWidth: 1 },
  teamRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  team: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
  gradeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  // Fixed width: the text column never depends on the grade's glyph widths.
  gradeBox: { width: 92, flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'center', gap: 3 },
  grade: { fontSize: 66, lineHeight: 70, fontWeight: '900' },
  modifier: { width: 26, height: 26, borderRadius: 13, borderWidth: 2, alignItems: 'center', justifyContent: 'center', marginTop: 6 },
  modifierText: { fontSize: 18, lineHeight: 20, fontWeight: '900', textAlign: 'center' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  headline: { flexShrink: 1, fontSize: 19, fontWeight: '900', color: colors.textPrimary },
  subline: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, marginTop: 2 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 },
  tag: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: 6, paddingHorizontal: spacing.sm, borderLeftWidth: 4, borderRadius: radii.md },
  photo: { backgroundColor: colors.surface },
  initials: { alignItems: 'center', justifyContent: 'center' },
  initialsText: { fontWeight: '800' },
  glyphDisc: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  rowText: { flex: 1, minWidth: 0 },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  kind: { fontSize: 10, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
  rowTitle: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
  meta: { fontSize: 10, fontWeight: '600', color: colors.textTertiary },
  delta: { fontSize: 14, fontWeight: '900' },
  stats: { flexDirection: 'row', gap: spacing.xs },
  stat: { flex: 1, padding: spacing.sm, justifyContent: 'space-between', gap: 2 },
  statValue: { fontSize: 16, fontWeight: '900', color: colors.textPrimary },
});
