"use client";

import { useId, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { Sheet } from "@/components/ui/Sheet";
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
} from "@/lib/filterSheet";

import "./ui.css";

export type FilterSheetProps = {
  /** Sheet heading. */
  title?: string;
  groups: readonly FilterGroup[];
  /** Committed filters (what the page is filtering by right now). */
  values: FilterValues;
  /** Called with the draft when the person taps Apply. */
  onApply: (next: FilterValues) => void;
  /**
   * Live result count for a draft, so the footer reads "Show 24 results" and
   * "No results" before anything is committed. Return null while unknown.
   */
  resultCount?: (draft: FilterValues) => number | null;
  /** Show removable chips for the active filters under the trigger. Default true. */
  showChips?: boolean;
  className?: string;
  testId?: string;
};

/**
 * One "Filters (n)" button that opens a Sheet of grouped chips, committed
 * with Apply. Replaces a row of native dropdowns and pill rows. The sheet
 * edits a draft: nothing on the page changes until Apply, and closing
 * discards. Active filters show as removable chips under the button.
 *
 * a11y: the sheet is a form (a fieldset and legend per group); single-select
 * groups are radio groups, multi-select groups are toggle buttons with
 * aria-pressed; the count is on the trigger's accessible name; the footer
 * count is a polite live region.
 */
export function FilterSheet({ title = "Filters", groups, values, onApply, resultCount, showChips = true, className = "", testId }: FilterSheetProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<FilterValues>(values);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const baseId = useId();
  const count = activeFilterCount(groups, values);
  const chips = showChips ? activeFilterChips(groups, values) : [];
  const shown = visibleGroups(groups);
  const live = resultCount ? resultCount(draft) : null;

  function openSheet() {
    setDraft(values); // always start from what is committed
    setOpen(true);
  }

  return (
    <div className={`ui-fs ${className}`.trim()} data-testid={testId}>
      <div className="ui-fs-bar">
        <button
          ref={triggerRef}
          type="button"
          className={`ui-fs-trigger${count ? " ui-fs-trigger-on" : ""}`}
          aria-haspopup="dialog"
          aria-label={filterTriggerAria(count)}
          onClick={openSheet}
        >
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M2 4h12M4.5 8h7M7 12h2" />
          </svg>
          <span>Filters</span>
          {count ? (
            <span className="ui-fs-badge" aria-hidden="true">
              {count}
            </span>
          ) : null}
        </button>
        {chips.length ? (
          <ul className="ui-fs-chips" aria-label="Active filters">
            {chips.map((chip) => (
              <li key={`${chip.groupId}:${chip.value}`} className="ui-fs-active">
                <span>{chip.label}</span>
                <button type="button" aria-label={`Remove ${chip.groupLabel} filter: ${chip.label}`} onClick={() => onApply(removeFilterChip(values, chip))}>
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title={title}
        size="sm"
        footer={
          <div className="ui-fs-footer">
            <Button variant="ghost" size="sm" onClick={() => setDraft(clearFilters())} disabled={activeFilterCount(groups, draft) === 0}>
              Reset
            </Button>
            <Button
              fullWidth
              disabled={live === 0}
              onClick={() => {
                onApply(draft);
                setOpen(false);
              }}
            >
              <span aria-live="polite">{applyButtonLabel(live)}</span>
            </Button>
          </div>
        }
      >
        <form className="ui-fs-form" onSubmit={(event) => event.preventDefault()}>
          {shown.map((group) => (
            <fieldset key={group.id} className="ui-fs-group">
              <legend className="ui-fs-legend">{group.label}</legend>
              <div className="ui-fs-options" role={group.multi ? "group" : "radiogroup"} aria-label={group.label} id={`${baseId}-${group.id}`}>
                {group.options.map((option) => {
                  const selected = isChipSelected(group, draft, option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      role={group.multi ? undefined : "radio"}
                      aria-checked={group.multi ? undefined : selected}
                      aria-pressed={group.multi ? selected : undefined}
                      className={`ui-fs-option${selected ? " ui-fs-option-on" : ""}`}
                      onClick={() => setDraft((current) => toggleFilterValue(group, current, option.value))}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </form>
      </Sheet>
    </div>
  );
}
