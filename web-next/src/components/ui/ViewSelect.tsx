"use client";

import { Select } from "@/components/Input";

/**
 * The page's view selector (docs/ui-patterns.md, "One tab row, one control row"): when a page already has its family
 * tab strip, its own views (Recommended / Explore / Watchlist, Season Outlook / Pick'em, Recaps / Roundup / ...) are a
 * compact 44px select in the control row instead of a second tab row. Native select: accessible, one tap, no new
 * widget. Mobile twin: FilterDropdownButton with label "View".
 */
export function ViewSelect<T extends string>({
  value,
  options,
  onChange,
  label = "View",
  className = "",
}: {
  value: T;
  options: ReadonlyArray<{ value: T; label: string }>;
  onChange: (value: T) => void;
  label?: string;
  className?: string;
}) {
  return (
    <Select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value as T)}
      className={`font-bold ${className}`.trim()}
      style={{ minHeight: "var(--touch-target-min)" }}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </Select>
  );
}
