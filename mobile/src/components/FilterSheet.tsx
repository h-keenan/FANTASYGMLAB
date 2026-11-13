import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import { Sheet } from './Sheet';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  activeFilterChips,
  activeFilterCount,
  applyButtonLabel,
  clearFilters,
  filterTriggerAria,
  isChipSelected,
  removeFilterChip,
  toggleFilterValue,
  visibleGroups,
  type FilterGroup,
  type FilterValues,
} from '../lib/filterSheet';
import { radii, spacing, type ThemeColors } from '../theme';

export type FilterSheetProps = {
  /** Sheet heading. */
  title?: string;
  groups: readonly FilterGroup[];
  /** Committed filters (what the screen is filtering by right now). */
  values: FilterValues;
  /** Called with the draft when the person taps Apply. */
  onApply: (next: FilterValues) => void;
  /** Live result count for a draft, so the footer reads "Show 24 results" and "No results". */
  resultCount?: (draft: FilterValues) => number | null;
  /** Show removable chips for the active filters next to the trigger. Default true. */
  showChips?: boolean;
  testID?: string;
};

/**
 * Twin of web-next's components/ui/FilterSheet.tsx. One "Filters (n)" button
 * that opens a Sheet of grouped chips, committed with Apply; the sheet edits
 * a draft, closing discards. It extends FilterDropdownButton (one group per
 * pill) to many groups behind one control.
 */
export default function FilterSheet({ title = 'Filters', groups, values, onApply, resultCount, showChips = true, testID }: FilterSheetProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<FilterValues>(values);
  const count = activeFilterCount(groups, values);
  const chips = showChips ? activeFilterChips(groups, values) : [];
  const live = resultCount ? resultCount(draft) : null;

  return (
    <View style={styles.wrap} testID={testID}>
      <View style={styles.bar}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={filterTriggerAria(count)}
          accessibilityHint="Opens filter options"
          onPress={() => {
            setDraft(values);
            setOpen(true);
          }}
          style={({ pressed }) => [styles.trigger, count > 0 && styles.triggerOn, pressed && styles.pressed]}
        >
          <Ionicons name="options-outline" size={16} color={count > 0 ? colors.accent : colors.textSecondary} />
          <AppText style={[styles.triggerText, count > 0 && { color: colors.accent }]}>Filters</AppText>
          {count > 0 ? (
            <View style={styles.badge}>
              <AppText style={styles.badgeText}>{count}</AppText>
            </View>
          ) : null}
        </Pressable>
        {chips.map((chip) => (
          <Pressable
            key={`${chip.groupId}:${chip.value}`}
            accessibilityRole="button"
            accessibilityLabel={`Remove ${chip.groupLabel} filter: ${chip.label}`}
            onPress={() => onApply(removeFilterChip(values, chip))}
            style={styles.active}
            hitSlop={6}
          >
            <AppText style={styles.activeText}>{chip.label}</AppText>
            <Ionicons name="close" size={14} color={colors.accent} />
          </Pressable>
        ))}
      </View>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title={title}
        size="sm"
        footer={
          <View style={styles.footer}>
            <Button label="Reset" variant="ghost" size="sm" onPress={() => setDraft(clearFilters())} disabled={activeFilterCount(groups, draft) === 0} />
            <Button
              label={applyButtonLabel(live)}
              disabled={live === 0}
              onPress={() => {
                onApply(draft);
                setOpen(false);
              }}
              style={styles.apply}
            />
          </View>
        }
      >
        {visibleGroups(groups).map((group) => (
          <View key={group.id} style={styles.group} accessibilityRole={group.multi ? undefined : 'radiogroup'}>
            <AppText style={styles.legend} accessibilityRole="header">
              {group.label}
            </AppText>
            <View style={styles.options}>
              {group.options.map((option) => {
                const selected = isChipSelected(group, draft, option.value);
                return (
                  <Pressable
                    key={option.value}
                    accessibilityRole={group.multi ? 'button' : 'radio'}
                    accessibilityState={group.multi ? { selected } : { checked: selected }}
                    onPress={() => setDraft((current) => toggleFilterValue(group, current, option.value))}
                    style={[styles.option, selected && styles.optionOn]}
                  >
                    <AppText style={[styles.optionText, selected && { color: colors.accent }]}>{option.label}</AppText>
                  </Pressable>
                );
              })}
            </View>
          </View>
        ))}
      </Sheet>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { minWidth: 0 },
    bar: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    trigger: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      minHeight: 44,
      paddingHorizontal: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.borderStrong,
    },
    triggerOn: { borderColor: colors.accent },
    triggerText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    badge: { minWidth: 20, height: 20, paddingHorizontal: 4, borderRadius: radii.pill, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent },
    badgeText: { fontSize: 12, fontWeight: '800', color: colors.onAccent },
    pressed: { opacity: 0.7 },
    active: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      minHeight: 36,
      paddingHorizontal: spacing.md,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    activeText: { fontSize: 13, fontWeight: '700', color: colors.accent },
    footer: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    apply: { flex: 1 },
    group: { gap: spacing.sm },
    legend: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    options: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    option: {
      minHeight: 44,
      paddingHorizontal: spacing.lg,
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.borderStrong,
    },
    optionOn: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
    optionText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  });
}
