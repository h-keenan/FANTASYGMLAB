// Pure model for `FilterSheet` (web + mobile twins): one "Filters (n)" button
// that opens a sheet of grouped chips, committed with Apply. The sheet edits a
// DRAFT; nothing on the page changes until Apply, and closing discards.
//
// A group is either single-select (radio-like: one value, or the "any" choice
// when the group has one) or multi-select. Values are strings. The committed
// filter state is a plain `Record<groupId, string[]>`; a missing or empty
// entry means "no filter on this group".

export type FilterOption = { value: string; label: string };

export type FilterGroup = {
  id: string;
  label: string;
  options: readonly FilterOption[];
  /** Allow more than one chip selected. Default false (pick one). */
  multi?: boolean;
  /**
   * Value that means "no filter" for a single-select group (for example "ALL").
   * Selecting it, or tapping the selected chip again, clears the group, and it
   * is never counted as an active filter.
   */
  anyValue?: string;
  /** Hide the group entirely (for example Roster when ownership is unknown). */
  hidden?: boolean;
};

export type FilterValues = Record<string, string[]>;

export type ActiveFilterChip = { groupId: string; value: string; label: string; groupLabel: string };

export function visibleGroups(groups: readonly FilterGroup[]): FilterGroup[] {
  return groups.filter((group) => !group.hidden);
}

function isActiveValue(group: FilterGroup, value: string): boolean {
  return value !== "" && value !== group.anyValue;
}

/** Values that actually filter (never the "any" choice). */
export function activeValues(group: FilterGroup, values: FilterValues): string[] {
  return (values[group.id] ?? []).filter((value) => isActiveValue(group, value));
}

/** The number on the trigger badge: how many chips are filtering. */
export function activeFilterCount(groups: readonly FilterGroup[], values: FilterValues): number {
  return visibleGroups(groups).reduce((total, group) => total + activeValues(group, values).length, 0);
}

export function toggleFilterValue(group: FilterGroup, values: FilterValues, value: string): FilterValues {
  const current = values[group.id] ?? [];
  let next: string[];
  if (group.multi) {
    next = current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value];
  } else if (!isActiveValue(group, value) || current.includes(value)) {
    next = [];
  } else {
    next = [value];
  }
  return { ...values, [group.id]: next };
}

export function clearFilters(): FilterValues {
  return {};
}

/** Is this chip shown as selected? The "any" chip is selected when nothing else is. */
export function isChipSelected(group: FilterGroup, values: FilterValues, value: string): boolean {
  if (value === group.anyValue) return activeValues(group, values).length === 0;
  return (values[group.id] ?? []).includes(value);
}

/** Removable chips for the strip under the trigger. */
export function activeFilterChips(groups: readonly FilterGroup[], values: FilterValues): ActiveFilterChip[] {
  const chips: ActiveFilterChip[] = [];
  for (const group of visibleGroups(groups)) {
    for (const value of activeValues(group, values)) {
      const option = group.options.find((entry) => entry.value === value);
      chips.push({ groupId: group.id, value, label: option?.label ?? value, groupLabel: group.label });
    }
  }
  return chips;
}

export function removeFilterChip(values: FilterValues, chip: Pick<ActiveFilterChip, "groupId" | "value">): FilterValues {
  return { ...values, [chip.groupId]: (values[chip.groupId] ?? []).filter((value) => value !== chip.value) };
}

/** Footer button text: "Show 24 results", or just "Apply" while the count is unknown. */
export function applyButtonLabel(resultCount: number | null | undefined): string {
  if (resultCount == null) return "Apply";
  if (resultCount === 0) return "No results";
  return `Show ${resultCount} result${resultCount === 1 ? "" : "s"}`;
}

/** Accessible name for the trigger. */
export function filterTriggerAria(count: number): string {
  return count > 0 ? `Filters, ${count} active` : "Filters, none active";
}

/** Build the initial committed values from per-group single values (the shape page state usually has). */
export function valuesFromSingles(groups: readonly FilterGroup[], singles: Record<string, string>): FilterValues {
  const out: FilterValues = {};
  for (const group of groups) {
    const value = singles[group.id];
    out[group.id] = value && isActiveValue(group, value) ? [value] : [];
  }
  return out;
}

/** The single selected value of a group, or its `anyValue` (or "") when none. */
export function singleValue(group: FilterGroup, values: FilterValues): string {
  return activeValues(group, values)[0] ?? group.anyValue ?? "";
}
