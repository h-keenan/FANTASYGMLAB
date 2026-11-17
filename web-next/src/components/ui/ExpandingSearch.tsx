"use client";

import { useEffect, useRef } from "react";

/**
 * Search in a crowded control row: collapsed it is a 44px search icon button (so the row's tabs and Filters keep their room and a
 * placeholder is never squeezed to "Sear"); tapped, it fills the row (the parent hides its other controls while `open`) with the
 * field and a Close button. A non-empty query stays open. Mobile twin: components/ExpandingSearch.tsx.
 */
export function ExpandingSearch({
  value,
  onChange,
  open,
  onOpenChange,
  label = "Search",
  placeholder = "Search",
}: {
  value: string;
  onChange: (next: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label?: string;
  placeholder?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (!open) {
    return (
      <button
        type="button"
        aria-label={label}
        onClick={() => onOpenChange(true)}
        className="filter-input inline-flex shrink-0 items-center justify-center"
        style={{ width: "var(--touch-target-min)", minHeight: "var(--touch-target-min)", color: value ? "var(--color-accent)" : "var(--color-text-secondary)" }}
        data-testid="search-open"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3.5-3.5" />
        </svg>
      </button>
    );
  }
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2" data-testid="search-expanded">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={label}
        className="filter-input min-w-0 flex-1 px-3 py-2 text-sm"
        style={{ minHeight: "var(--touch-target-min)" }}
      />
      <button
        type="button"
        onClick={() => {
          onChange("");
          onOpenChange(false);
        }}
        className="shrink-0 px-2 text-sm font-bold"
        style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)" }}
      >
        Close
      </button>
    </div>
  );
}
