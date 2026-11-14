import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import { ReviewGlyphChip } from './SeasonReviewSections';
import { SimCollapse } from './SimGameDynastyParts';
import { SimPopIn, SimToneBadge, createSimStyles, simToneColor } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  simDynastySummaryView,
  simDynastyYearView,
  type SimDynastySummary,
  type SimDynastyYear,
  type SimDynastyYearView,
} from '../lib/simGame';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * A small per-year strip: one cell per finished season with the year, record
 * and finish. Scrolls inside its own box, so the page never scrolls sideways.
 */
export function SimDynastyStrip({ years }: { years: SimDynastyYear[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (years.length === 0) return null;
  const views = years.map(simDynastyYearView);
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} testID="dynasty-strip" accessibilityLabel="Your seasons so far">
      {views.map((v) => (
        <View key={v.year} style={[styles.cell, { borderTopColor: v.youWon ? colors.success : simToneColor(v.resultTone, colors) }]}>
          <View style={styles.cellTop}>
            <AppText style={styles.cellYear}>{v.label}</AppText>
            {v.youWon ? <ReviewGlyphChip glyph="trophy" tone="success" size={18} /> : null}
          </View>
          <AppText style={styles.cellRecord}>{v.record}</AppText>
          <AppText style={styles.cellMeta}>
            {v.finish} · {v.result}
          </AppText>
        </View>
      ))}
    </ScrollView>
  );
}

function YearRow({ v }: { v: SimDynastyYearView }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <View style={[common.tight, common.divider, { paddingVertical: spacing.sm }]} testID="dynasty-year">
      <View style={common.rowBetween}>
        <AppText style={common.bodyStrong}>{v.label}</AppText>
        <View style={[common.wrapRow, { justifyContent: 'flex-end', flexShrink: 1 }]}>
          <AppText style={common.bodyStrong}>{v.record}</AppText>
          <SimToneBadge label={`${v.finish} place`} tone="muted" />
          <SimToneBadge label={v.result} tone={v.resultTone} />
        </View>
      </View>
      <AppText style={[common.muted, v.youWon && { color: colors.success }]}>Champion: {v.champion}</AppText>
      {v.scorers ? <AppText style={common.small}>Top scorers: {v.scorers}</AppText> : null}
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.fact}>
      <AppText style={styles.factLabel}>{label}</AppText>
      <AppText style={styles.factValue}>{value}</AppText>
    </View>
  );
}

/**
 * The dynasty result: titles, average finish, best season and a per-year
 * list. A dynasty game has no grade, so this stands where the grade card does.
 */
export function SimDynastyResult({ summary, onNewGame, onHub }: { summary: SimDynastySummary | null | undefined; onNewGame: () => void; onHub: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const view = simDynastySummaryView(summary);
  const champion = view.titles > 0;
  return (
    <View style={common.stack} testID="dynasty-result">
      <AccentCard accent={champion ? colors.success : colors.accent} glow={champion}>
        <AppText style={styles.kicker}>Dynasty in review</AppText>
        <SimPopIn>
          <View style={common.row}>
            <ReviewGlyphChip glyph="trophy" tone={champion ? 'success' : 'accent'} size={32} />
            <AppText style={[common.title, common.grow, champion && { color: colors.success }]}>{view.titlesLine}</AppText>
          </View>
        </SimPopIn>
        <AppText style={common.muted}>{view.seasonsLine}</AppText>
        <View style={styles.facts}>
          <Fact label="Average finish" value={view.avgFinish} />
          <Fact label="Best season" value={view.bestSeason} />
          <Fact label="Playoff trips" value={view.trips} />
          <Fact label="Record" value={view.record} />
        </View>
        <View style={common.wrapRow}>
          <Button label="Play again" onPress={onNewGame} />
          <Button variant="secondary" label="All games" onPress={onHub} />
        </View>
      </AccentCard>
      <SimCollapse title="Season by season" summary={view.years.length ? `${view.years.length} seasons` : 'No seasons yet'} defaultOpen testID="dynasty-years">
        {view.years.length === 0 ? <AppText style={common.muted}>No finished seasons to show.</AppText> : view.years.map((v) => <YearRow key={v.year} v={v} />)}
      </SimCollapse>
      {view.history.champions.length > 0 ? (
        <SimCollapse title="League history" summary={view.history.summary} testID="dynasty-history">
          {view.history.champions.map((c) => (
            <AppText key={c.key} style={c.you ? common.bodyStrong : common.body}>{c.label}</AppText>
          ))}
          {[...view.history.leaders, ...view.history.records].map((line) => (
            <AppText key={line} style={common.muted}>{line}</AppText>
          ))}
        </SimCollapse>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    strip: { gap: spacing.sm, paddingBottom: spacing.xs },
    cell: {
      minWidth: 96,
      gap: 2,
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.sm,
      borderRadius: radii.md,
      borderWidth: 1,
      borderTopWidth: 3,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    cellTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    cellYear: { fontSize: 13, fontWeight: '800', color: colors.textPrimary },
    cellRecord: { fontSize: 13, color: colors.textSecondary },
    cellMeta: { fontSize: 12, color: colors.textTertiary },
    facts: { flexDirection: 'row', flexWrap: 'wrap', rowGap: spacing.md },
    fact: { width: '50%', paddingRight: spacing.sm },
    factLabel: { fontSize: 12, color: colors.textTertiary },
    factValue: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
  });
}
