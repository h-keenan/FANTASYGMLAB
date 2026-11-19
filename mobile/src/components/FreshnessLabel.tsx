import React, { useMemo, useState } from 'react';
import { StyleSheet, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { freshnessLabel, leagueStaleLabel, type FreshnessDataset, type FreshnessReport } from '../lib/dataFreshness';
import { useDataFreshness } from '../lib/useDataFreshness';
import { typography, type ThemeColors } from '../theme';

/**
 * THE "as of" line for data that can be stale (data-truth audit 2026-11-19, finding 4): "Values as of 2h ago",
 * "Injuries updated 9:40am". Every surface uses this one component with the datasets it shows; wording, thresholds and the
 * honesty rules (no timestamp means no label) live in lib/dataFreshness.ts. Muted text, never an error colour. Renders
 * nothing until the public report loads or when it cannot say. Web twin: web-next/src/components/ui/FreshnessLabel.tsx.
 */
export default function FreshnessLabel({
  datasets,
  report,
  now,
  leagueAsOf,
  style,
}: {
  datasets: readonly FreshnessDataset[];
  report?: FreshnessReport | null;
  now?: number;
  /** The league response's `sleeper_data_as_of`: set only when the API served last-known provider data. */
  leagueAsOf?: string | null;
  style?: StyleProp<TextStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const fetched = useDataFreshness(report === undefined && datasets.length > 0);
  const source = report === undefined ? fetched : report;
  const [mountedAt] = useState(() => Date.now());
  const at = now ?? mountedAt;
  const labels = datasets.map((dataset) => freshnessLabel(source, dataset, at)).filter((text): text is string => Boolean(text));
  const stale = leagueStaleLabel(leagueAsOf, at);
  if (stale) labels.push(stale);
  if (labels.length === 0) return null;
  return (
    <AppText style={[styles.text, style]} testID="freshness-label">
      {labels.join(' · ')}
    </AppText>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    text: { ...typography.caption, color: colors.textTertiary, textAlign: 'center' },
  });
}
