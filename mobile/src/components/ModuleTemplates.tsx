import React, { useMemo, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import CompactModule from './CompactModule';
import DashboardStatRow, { type StatStripItem } from './DashboardStatRow';
import TrendChart from './TrendChart';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ChartInputPoint } from '../lib/chartSeries';
import { compactAriaLabel, compactParts, type CompactPart, type CompactTone } from '../lib/compactModule';
import { heroParts, statStripParts, trendModel, type TrendModel } from '../lib/moduleTemplates';
import { spacing, type ThemeColors } from '../theme';

/**
 * The module template components (mirrors web-next/src/components/ui/ModuleTemplates.tsx; catalog in
 * lib/moduleTemplates.ts, docs/ui-patterns.md "Module templates"). CompactModule is the base; Hero, StatStripModule and
 * LinkModule are the shapes built on it or beside it.
 */

function toneColor(tone: CompactTone | undefined, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent':
    case 'action': return colors.accent;
    case 'muted': return colors.textTertiary;
    default: return colors.textPrimary;
  }
}

export function Hero({
  label,
  value,
  context,
  trendPoints,
  trendHigherIsBetter = true,
  trendDigits = 1,
  tone = 'accent',
  badge,
  action,
  onPress,
  testID,
  trendName,
}: {
  label: string;
  value: string;
  context?: string | null;
  trendPoints?: ReadonlyArray<number | null | undefined>;
  trendHigherIsBetter?: boolean;
  trendDigits?: number;
  tone?: CompactTone;
  badge?: ReactNode;
  action?: ReactNode;
  onPress?: () => void;
  testID?: string;
  trendName?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const trend: TrendModel | null = trendPoints ? trendModel(trendPoints, trendHigherIsBetter, trendDigits) : null;
  const chartPoints: ChartInputPoint[] | null =
    trendPoints && trend ? trendPoints.map((y, i) => ({ x: i, y: typeof y === 'number' ? y : null })) : null;
  const name = compactAriaLabel(label, heroParts({ label, value, context, trend }), false).replace(/\. (Expand|Collapse)$/, '');
  return (
    <AccentCard accent={toneColor(tone, colors)} onPress={onPress}>
      <View accessible accessibilityLabel={name} accessibilityRole={onPress ? 'button' : undefined} testID={testID ?? 'hero'}>
        <View style={styles.row}>
          <AppText style={styles.label}>{label}</AppText>
          {badge}
        </View>
        <View style={styles.valueRow}>
          <AppText style={styles.value} testID="hero-value">{value}</AppText>
          {trend ? (
            <AppText style={[styles.trend, { color: toneColor(trend.tone, colors) }]} testID="hero-trend">
              {trend.direction === 'up' ? '▲' : trend.direction === 'down' ? '▼' : '–'} {trend.label}
            </AppText>
          ) : null}
          {chartPoints ? (
            <View style={styles.spark} accessibilityElementsHidden>
              <TrendChart points={chartPoints} name={trendName ?? label} variant="compact" height={40} />
            </View>
          ) : null}
        </View>
        {context ? <AppText style={styles.context} testID="hero-context">{context}</AppText> : null}
      </View>
      {action ? <View style={styles.action}>{action}</View> : null}
    </AccentCard>
  );
}

const SHORT: Record<string, string> = {
  'Power Rank': 'Power',
  'Franchise Rank': 'Franchise',
  'Starter Strength': 'Starters',
  'Bench Strength': 'Bench',
  'Avg Age': 'Age',
  'Average Age': 'Age',
  'Injured starters': 'Injured',
};

/** "Power Rank" -> "Power": the summary line uses the short noun. */
export function shortLabel(label: string): string {
  return SHORT[label] ?? label;
}

/** Stat tiles as a module: collapsed shows "Power #3 · Starters #5 · Age 26.1", expanded the full tiles. */
export function StatStripModule({
  id,
  title,
  items,
  columns = 3,
  defaultOpen = false,
  tone = 'accent',
  action,
  extraParts,
  footer,
  testID,
}: {
  id: string;
  title: string;
  items: StatStripItem[];
  columns?: number;
  defaultOpen?: boolean;
  tone?: CompactTone;
  action?: ReactNode;
  extraParts?: ReadonlyArray<CompactPart | null | undefined | false | ''>;
  /** Shown under the tiles when expanded (glossary, beginner help). */
  footer?: ReactNode;
  testID?: string;
}) {
  const parts = compactParts([
    ...statStripParts(
      items.map((i) => ({
        label: shortLabel(i.label),
        value: i.value,
        tone: i.tone === 'risk' ? ('danger' as const) : i.tone === 'positive' ? ('success' as const) : undefined,
      })),
    ),
    ...(extraParts ?? []),
  ]);
  const rows: StatStripItem[][] = [];
  for (let i = 0; i < items.length; i += columns) rows.push(items.slice(i, i + columns));
  return (
    <CompactModule id={id} title={title} parts={parts} tone={tone} defaultOpen={defaultOpen} action={action} testID={testID}>
      {rows.map((row, i) => (
        <DashboardStatRow key={i} items={row} />
      ))}
      {footer}
    </CompactModule>
  );
}

/** A compact summary that goes to another screen (a pointer, not an expander). */
export function LinkModule({
  title,
  parts,
  onPress,
  tone = 'accent',
  testID,
}: {
  title: string;
  parts: ReadonlyArray<CompactPart | null | undefined | false | ''>;
  onPress: () => void;
  tone?: CompactTone;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const shown = compactParts(parts);
  return (
    <AccentCard accent={toneColor(tone, colors)} compact>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={`${title}: ${shown.map((p) => p.text).join(' · ')}. Open`}
        onPress={onPress}
        style={styles.link}
        testID={testID}
      >
        <View style={{ flex: 1, minWidth: 0 }}>
          <AppText style={styles.label}>{title}</AppText>
          <AppText style={styles.parts} numberOfLines={2} testID="compact-summary">
            {shown.map((part, i) => (
              <AppText key={part.key} style={[styles.part, part.tone ? { color: toneColor(part.tone, colors) } : null, part.strong ? { fontWeight: '800' } : null]}>
                {i > 0 ? <AppText style={styles.sep}>{' · '}</AppText> : null}
                {part.text}
              </AppText>
            ))}
          </AppText>
        </View>
        <AppText style={{ color: colors.accent }}>→</AppText>
      </Pressable>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    label: { fontSize: 12, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.6, color: colors.textTertiary },
    valueRow: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.md },
    value: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: colors.textPrimary },
    trend: { fontSize: 14, fontWeight: '800', paddingBottom: 4 },
    spark: { marginLeft: 'auto', width: 96, height: 40 },
    context: { fontSize: 14, color: colors.textSecondary },
    action: { flexDirection: 'row' },
    link: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    parts: { fontSize: 14, lineHeight: 19, color: colors.textPrimary },
    part: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
    sep: { color: colors.textTertiary, fontWeight: '400' },
  });
}
