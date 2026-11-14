import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { Sheet } from './Sheet';
import { withAlpha } from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  simAttributeText,
  simGradeAria,
  simGradeFill,
  simGradeLegend,
  simGradeRangeText,
  simGradeText,
  simGradeTone,
  type SimAttributeGrade,
  type SimGradeInput,
  type SimGradeTone,
} from '../lib/simGrade';
import { spacing, type ThemeColors } from '../theme';

/** The ramp: green, cyan, gold, orange, red, from existing theme tokens only (twin of web ui/LetterGrade.tsx). */
function toneColor(tone: SimGradeTone, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'accent': return colors.accent;
    case 'gold': return colors.premium;
    case 'warning': return colors.warning;
    default: return colors.danger;
  }
}

const SIZE = { xs: { h: 20, min: 26, font: 13 }, sm: { h: 24, min: 34, font: 13 }, md: { h: 32, min: 44, font: 16 }, lg: { h: 48, min: 64, font: 24 } } as const;

/**
 * The Fantasy Sim's overall: a Madden / 2K style letter grade instead of the numeric OVR gauge. Tinted capsule (same recipe as
 * PlayerBadge); the text keeps the primary colour for contrast. "?" = a scouting estimate (rookies). The full read is the
 * accessibility label. Reserves its footprint when there is no grade so list columns align.
 */
export function LetterGrade({ grade, size = 'sm', testID = 'letter-grade' }: { grade: SimGradeInput | null | undefined; size?: keyof typeof SIZE; testID?: string }) {
  const { colors } = useThemeMode();
  const spec = SIZE[size];
  if (!grade?.grade) return <View style={{ minWidth: spec.min, height: spec.h }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />;
  const color = toneColor(simGradeTone(grade.grade), colors);
  const range = simGradeRangeText(grade);
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={simGradeAria(grade)}
      testID={testID}
      style={[styles.capsule, size === 'xs' && { borderRadius: 6, paddingHorizontal: 5 }, { minWidth: spec.min, height: spec.h, backgroundColor: withAlpha(color, 0.15), borderColor: withAlpha(color, 0.55) }]}
    >
      {size === 'xs' && grade.grade_uncertain ? (
        <AppText style={{ fontSize: spec.font, fontWeight: '800', lineHeight: spec.font + 2, color: colors.textPrimary }} importantForAccessibility="no">
          {grade.grade}
          <AppText style={{ fontSize: 12, fontWeight: '700', color: colors.textTertiary }} importantForAccessibility="no">?</AppText>
        </AppText>
      ) : (
        <AppText style={{ fontSize: spec.font, fontWeight: '800', lineHeight: spec.font + 2, color: colors.textPrimary }} importantForAccessibility="no">{simGradeText(grade)}</AppText>
      )}
      {size === 'lg' && range ? <AppText style={{ fontSize: 12, fontWeight: '700', color: colors.textTertiary }} importantForAccessibility="no">{range}</AppText> : null}
    </View>
  );
}

/** One attribute row: label, a coarse bar tinted by the grade tone, and the letter. */
export function GradeBar({ attribute }: { attribute: SimAttributeGrade }) {
  const { colors } = useThemeMode();
  const color = toneColor(simGradeTone(attribute.grade), colors);
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={`${attribute.label}: ${simGradeAria({ grade: attribute.grade, grade_uncertain: attribute.uncertain })}`}
      style={styles.barRow}
      testID="grade-bar"
    >
      <AppText style={{ width: 96, fontSize: 12, fontWeight: '700', color: colors.textTertiary }} importantForAccessibility="no">{attribute.label}</AppText>
      <View style={[styles.track, { backgroundColor: withAlpha(colors.textTertiary, 0.18) }]}>
        <View style={{ width: `${simGradeFill(attribute.grade)}%`, height: '100%', backgroundColor: color, borderRadius: 999 }} />
      </View>
      <AppText style={{ width: 36, textAlign: 'right', fontSize: 14, fontWeight: '800', color: colors.textPrimary }} importantForAccessibility="no">{simAttributeText(attribute)}</AppText>
    </View>
  );
}

/** The legend sheet: every grade and what it means, and what the "?" and the attributes are. */
export function GradeLegendSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { colors } = useThemeMode();
  return (
    <Sheet open={open} onClose={onClose} title="What the grades mean">
      <View testID="grade-legend">
        <AppText style={{ fontSize: 12, color: colors.textTertiary, paddingBottom: spacing.sm }}>
          A grade is the scouts' read of a player against his position, not an exact number: two players can share a grade, and a scout can be off by a step. A "?" means the scouts are unsure (rookies), so the grade could land a step either side.
        </AppText>
        {simGradeLegend().map((row) => (
          <View key={row.grade} style={[styles.legendRow, { borderBottomColor: colors.border }]}>
            <LetterGrade grade={{ grade: row.grade }} testID="legend-grade" />
            <AppText style={{ flex: 1, fontSize: 14, color: colors.textPrimary }}>{row.meaning}</AppText>
          </View>
        ))}
        <AppText style={{ fontSize: 12, color: colors.textTertiary, paddingTop: spacing.sm }}>
          Attribute bars (Production, Volume, Durability and so on) come from usage and history and are graded on their own. They do not add up to the overall.
        </AppText>
      </View>
    </Sheet>
  );
}

/** A small "Grades" key button for a list header: opens the legend sheet. */
export function GradeLegendButton() {
  const { colors } = useThemeMode();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel="What the grades mean" style={styles.keyButton}>
        <AppText style={{ fontSize: 12, fontWeight: '800', color: colors.textTertiary }}>ⓘ Grades</AppText>
      </Pressable>
      <GradeLegendSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}

const styles = StyleSheet.create({
  capsule: { paddingHorizontal: 8, borderRadius: 999, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  barRow: { flexDirection: 'row', alignItems: 'center', columnGap: spacing.md },
  track: { flex: 1, height: 8, borderRadius: 999, overflow: 'hidden' },
  legendRow: { flexDirection: 'row', alignItems: 'center', columnGap: spacing.md, paddingVertical: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth },
  keyButton: { minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' },
});

/** The quick view hero's grade tile: the big grade, tappable to open the legend (44pt target). */
export function GradeTile({ grade, style }: { grade: SimGradeInput | null | undefined; style?: object }) {
  const { colors } = useThemeMode();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel={`${simGradeAria(grade)}. What the grades mean`} style={[{ minHeight: 44, alignItems: 'center', justifyContent: 'center', rowGap: 4 }, style]} testID="hero-grade">
        <LetterGrade grade={grade} size="lg" testID="hero-letter-grade" />
        <AppText style={{ fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary }}>GRADE</AppText>
      </Pressable>
      <GradeLegendSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}
