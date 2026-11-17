"use client";

import { PillRow } from "@/components/PillRow";

/**
 * A page's view switch with FOUR OR FEWER options (Season Outlook / Pick'em, Players / Prospects, NFL / My League, Recommended /
 * Explore / Watchlist ...): the shared compact segmented tabs (`PillRow variant="compact"`, ~40px, about the height of the select it
 * replaces), never a dropdown. Five or more options (seasons, weeks, long lists) use `ViewSelect`. `scripts/check_view_select.mjs`
 * fails a `ViewSelect` with four or fewer options. Same props as `ViewSelect`. Mobile twin: `ViewTabs` in components/PageControlRow.tsx.
 */
export function ViewTabs<T extends string>({
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
    <div className={`min-w-0 ${className}`.trim()} data-testid="view-tabs">
      <PillRow
        variant="compact"
        ariaLabel={label}
        options={options.map((o) => ({ label: o.label, value: o.value }))}
        active={value}
        onSelect={(next) => onChange(next as T)}
      />
    </div>
  );
}
