import React from 'react';
import { StyleSheet, View } from 'react-native';

import FilterDropdownButton from './FilterDropdownButton';
import { PAGE_TOP_GAP, spacing } from '../theme';

/**
 * THE one control row of a page (UI audit batch H, docs/audits/2026-11-ui-audit-e2e.md P0-2): the page's own view switch (Players /
 * Prospects, NFL / My League, Season Outlook / Pick'em) and its filters share ONE 44pt line, then `PAGE_TOP_GAP` to the first module.
 * No stacked tab / filter / pill rows. Build it from `ViewSelect` (a "View" select), FilterSheet (one Filters button) and
 * FilterDropdownButton; every child keeps its own 44pt tap target and may shrink, so the row never wraps.
 * Web twin: web-next/src/components/ui/PageControls.tsx (PageControlsRow).
 */
export default function PageControlRow({ children, testID = 'page-controls' }: { children?: React.ReactNode; testID?: string }) {
  return (
    <View style={styles.row} testID={testID}>
      {children}
    </View>
  );
}

/** A view / section select for a PageControlRow: reads its current value, opens the shared option sheet. */
export function ViewSelect<T extends string>({
  label = 'View',
  options,
  value,
  onChange,
  testID,
}: {
  label?: string;
  options: readonly T[];
  value: T;
  onChange: (next: T) => void;
  testID?: string;
}) {
  return <FilterDropdownButton<T> select label={label} options={options} value={value} onChange={onChange} testID={testID} />;
}

/** "Wk N" select for a PageControlRow (replaces the week strip); renders nothing with fewer than two weeks. */
export function WeekSelect({ weeks, value, onChange }: { weeks: readonly number[]; value: number; onChange: (week: number) => void }) {
  if (weeks.length < 2) return null;
  const labels = weeks.map((w) => `Wk ${w}`);
  return (
    <FilterDropdownButton<string>
      select
      label="Week"
      options={labels}
      value={`Wk ${value}`}
      onChange={(label) => onChange(Number(label.replace('Wk ', '')))}
      testID="week-select"
    />
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, marginBottom: PAGE_TOP_GAP },
});
