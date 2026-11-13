"use client";

import { PlayerName } from "@/components/PlayerName";
import { useEffect, useId, useMemo, useReducer, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/Button";
import { PickRow } from "@/components/PickRow";
import { PillRow } from "@/components/PillRow";
import { PlayerIdentity } from "@/components/PlayerRow";
import { SheetHandle } from "@/components/SheetHandle";
import { ValueStat } from "@/components/ValueStat";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";
import {
  SHEET_CONDITIONS,
  activeFilterCount,
  applyLabel,
  filterSheetItems,
  filterSummary,
  filtersEmpty,
  groupSheetItems,
  initialSheetState,
  positionsFor,
  selectedItems,
  sheetReducer,
  summarizeItems,
  type SheetFilters,
  type SheetItem,
} from "@/lib/tradeSheetPicker";

/**
 * The shared trade piece picker. Tapping a side of a trade (You send / You get,
 * or one team of a multi-team trade) opens this as a bottom sheet on phones and
 * a centered dialog on desktop: a Players | Picks control, a search box, one
 * Filters button (position + condition chips, committed with Apply), the
 * selection as removable chips, 44px+ rows you tap to toggle, and a sticky
 * "Add N to trade" button. The player card (PQV) opens from the info button,
 * never from the row. Used by the Trade Analyzer, the multi-team builder and
 * the Fantasy Sim trade builder; logic lives in lib/tradeSheetPicker.ts.
 *
 * Mount it while it is open: it starts from `initialSelected` and hands the
 * whole selection back through `onApply`. Closing any other way discards.
 */
export function TradePickerSheet<T = unknown>({
  title,
  subtitle,
  tone,
  items,
  initialSelected,
  max,
  onApply,
  onClose,
  onInfo,
  onSearch,
  mode = "multi",
  initialFilters,
  renderPlayerRow,
  flexFilter = false,
}: {
  title: string;
  subtitle?: string;
  tone: "danger" | "success" | "neutral";
  items: SheetItem<T>[];
  initialSelected: string[];
  max?: number;
  onApply: (keys: string[]) => void;
  onClose: () => void;
  /** Opens the player card; rows never do. Omit to hide the info button. */
  onInfo?: (item: SheetItem<T>) => void;
  /** Called as the search text changes, so a caller can fetch matches outside its loaded window. */
  onSearch?: (query: string) => void;
  /** "single" is a pick-one flow (Player Compare): tapping a row chooses it and closes, no chips or footer. */
  mode?: "multi" | "single";
  /** Filters already in effect when the sheet opens (e.g. the same position as the player being compared). */
  initialFilters?: SheetFilters;
  /**
   * Render player rows with the caller's own row (Fantasy Sim: the shared PlayerListRow, tap the body for the
   * quick view, a checkbox as its action). Picks keep the built-in row, and the info button is not drawn.
   */
  renderPlayerRow?: (item: SheetItem<T>, control: { on: boolean; blocked: boolean; toggle: () => void }) => ReactNode;
  /** Offer a FLEX chip (RB / WR / TE) in the position filter. */
  flexFilter?: boolean;
}) {
  const [state, dispatch] = useReducer(sheetReducer, undefined, () => initialSheetState(initialSelected, firstTab(items, initialSelected), initialFilters));
  const titleId = useId();
  const filterPanelId = useId();
  const filterButtonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const { sheetRef, sheetStyle } = useSheetDragDismiss<HTMLDivElement>({ onDismiss: onClose });
  const filtersOpen = state.draft !== null;
  const single = mode === "single";

  const hasPicks = useMemo(() => items.some((i) => i.kind === "pick"), [items]);
  const positions = useMemo(() => positionsFor(items, flexFilter), [items, flexFilter]);
  const visible = useMemo(() => filterSheetItems(items, { tab: state.tab, query: state.query, filters: state.filters }), [items, state.tab, state.query, state.filters]);
  const chosen = useMemo(() => selectedItems(items, state.selected), [items, state.selected]);
  const summary = summarizeItems(chosen);
  const playerCount = useMemo(() => items.filter((i) => i.kind === "player").length, [items]);
  const pickCount = items.length - playerCount;
  const atMax = max != null && state.selected.length >= max;
  const filterCount = activeFilterCount(state.filters);

  // Scroll lock + focus in on open, focus back to the trigger on close.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    sheetRef.current?.focus({ preventScroll: true });
    return () => {
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.({ preventScroll: true });
    };
  }, [sheetRef]);

  // Move focus into the filter panel when it opens and back to its button when it closes.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (filtersOpen && !wasOpen.current) panelRef.current?.querySelector<HTMLElement>("button")?.focus({ preventScroll: true });
    if (!filtersOpen && wasOpen.current) filterButtonRef.current?.focus({ preventScroll: true });
    wasOpen.current = filtersOpen;
  }, [filtersOpen]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.stopPropagation();
      if (filtersOpen) dispatch({ type: "closeFilters" });
      else onClose();
      return;
    }
    if (event.key !== "Tab") return;
    // Focus trap: Tab cycles inside the dialog (inside the filter panel while it is open).
    const root = filtersOpen && panelRef.current ? panelRef.current : sheetRef.current;
    if (!root) return;
    const focusable = Array.from(root.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')).filter((el) => !el.closest('[aria-hidden="true"]'));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || !root.contains(active) || active === sheetRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || !root.contains(active))) {
      event.preventDefault();
      first.focus();
    }
  }

  const toneColor = tone === "danger" ? "var(--color-danger)" : tone === "success" ? "var(--color-success)" : "var(--color-accent)";
  const groups = state.tab === "picks" ? groupSheetItems(visible) : [{ key: "all", label: "", items: visible }];

  const dialog = (
    <div
      className="pqv-backdrop"
      data-sheet-hideable="true"
      data-testid="trade-picker-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={sheetRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="pqv-modal tps-modal"
        style={{ outline: "none", ...sheetStyle }}
        onKeyDown={onKeyDown}
        data-testid="trade-picker"
      >
        <SheetHandle />
        <header className="tps-header">
          <span aria-hidden="true" className="inline-block shrink-0" style={{ width: 8, height: 8, borderRadius: "50%", background: toneColor }} />
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-base font-extrabold truncate">
              {title}
            </h2>
            {subtitle ? (
              <p className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
                {subtitle}
              </p>
            ) : null}
          </div>
          <button type="button" className="pqv-close tps-close" aria-label={`Close ${title}`} onClick={onClose}>
            ×
          </button>
        </header>

        {!single && chosen.length > 0 ? (
          <ul className="tps-chips" aria-label="Selected">
            {chosen.map((item) => (
              <li key={item.key} className="tps-chip">
                {item.kind === "player" ? <PlayerName name={item.label} /> : <span className="truncate">{item.label}</span>}
                <button type="button" aria-label={`Remove ${item.label}`} onClick={() => dispatch({ type: "remove", key: item.key })}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="tps-controls">
          {hasPicks ? (
            <PillRow
              variant="fill"
              ariaLabel="Asset type"
              options={[
                { label: `Players ${playerCount}`, value: "players" },
                { label: `Picks ${pickCount}`, value: "picks" },
              ]}
              active={state.tab}
              onSelect={(value) => dispatch({ type: "tab", tab: value === "picks" ? "picks" : "players" })}
            />
          ) : null}
          <div className="flex items-center gap-2">
            <input
              type="search"
              inputMode="search"
              enterKeyHint="search"
              aria-label={state.tab === "picks" ? "Search picks" : "Search players"}
              placeholder={state.tab === "picks" ? "Search picks" : "Search players"}
              value={state.query}
              onChange={(event) => {
                dispatch({ type: "query", query: event.target.value });
                onSearch?.(event.target.value);
              }}
              className="glass-input min-w-0 flex-1 px-3 text-sm"
              style={{ minHeight: "var(--control-min-height)", color: "var(--color-text-primary)" }}
            />
            {state.tab === "players" ? (
              <button
                ref={filterButtonRef}
                type="button"
                className="tps-filter-button"
                aria-expanded={filtersOpen}
                aria-controls={filterPanelId}
                onClick={() => dispatch({ type: filtersOpen ? "closeFilters" : "openFilters" })}
              >
                Filters{filterCount ? ` (${filterCount})` : ""}
              </button>
            ) : null}
          </div>
          {state.tab === "players" && !filtersEmpty(state.filters) ? (
            <p className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              <span className="min-w-0 truncate">{filterSummary(state.filters)}</span>
              <button
                type="button"
                className="tap-link shrink-0 font-bold"
                style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
                aria-label="Clear filters"
                onClick={() => {
                  dispatch({ type: "openFilters" });
                  dispatch({ type: "clearDraft" });
                  dispatch({ type: "applyFilters" });
                }}
              >
                Clear
              </button>
            </p>
          ) : null}
        </div>

        <div className="tps-body">
          <ul className="tps-list" aria-label={state.tab === "picks" ? "Picks" : "Players"} aria-hidden={filtersOpen || undefined} style={filtersOpen ? { visibility: "hidden" } : undefined}>
            {visible.length === 0 ? (
              <li className="py-6 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
                {state.query || !filtersEmpty(state.filters) ? `No matching ${state.tab}.` : `No ${state.tab} available.`}
              </li>
            ) : (
              groups.map((group) => (
                <li key={group.key} className="contents">
                  {group.label ? (
                    <p className="px-1 pt-2 pb-1 text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                      {group.label}
                    </p>
                  ) : null}
                  <ul className="flex flex-col">
                    {group.items.map((item) => {
                      const on = state.selected.includes(item.key);
                      const blocked = !on && atMax;
                      if (renderPlayerRow && item.kind === "player") {
                        return (
                          <li key={item.key} className="tps-row-shared" data-selected={on ? "true" : "false"}>
                            {renderPlayerRow(item, { on, blocked, toggle: () => dispatch({ type: "toggle", key: item.key, max }) })}
                          </li>
                        );
                      }
                      return (
                        <li key={item.key} className="tps-row" data-selected={on ? "true" : "false"}>
                          <button
                            type="button"
                            className="tps-row-main"
                            aria-pressed={on}
                            disabled={blocked}
                            aria-label={single ? `Choose ${item.label}` : `${on ? "Remove" : "Add"} ${item.label}`}
                            onClick={() => (single ? onApply([item.key]) : dispatch({ type: "toggle", key: item.key, max }))}
                          >
                            <SheetItemIdentity item={item} />
                            {single ? null : (
                              <span className="tps-check" aria-hidden="true" data-on={on ? "true" : "false"}>
                                {on ? "✓" : ""}
                              </span>
                            )}
                          </button>
                          {onInfo && item.kind === "player" ? (
                            <button type="button" className="tps-info" aria-label={`${item.label} player card`} onClick={() => onInfo(item)}>
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                                <circle cx="12" cy="12" r="9" />
                                <path d="M12 11v5M12 7.5h.01" />
                              </svg>
                            </button>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))
            )}
          </ul>

          {filtersOpen && state.draft ? (
            <div ref={panelRef} id={filterPanelId} className="tps-filter-panel" role="group" aria-label="Filters">
              <div className="tps-filter-scroll">
                <FilterGroup title="Position">
                  {positions.map((position) => (
                    <FilterChip key={position} label={position} on={state.draft!.positions.includes(position)} onClick={() => dispatch({ type: "draftPosition", position })} />
                  ))}
                </FilterGroup>
                <FilterGroup title="Condition">
                  {SHEET_CONDITIONS.map((condition) => (
                    <FilterChip key={condition.value} label={condition.label} on={state.draft!.conditions.includes(condition.value)} onClick={() => dispatch({ type: "draftCondition", condition: condition.value })} />
                  ))}
                </FilterGroup>
              </div>
              <div className="tps-footer">
                <Button variant="secondary" onClick={() => dispatch({ type: "clearDraft" })}>
                  Clear
                </Button>
                <Button fullWidth onClick={() => dispatch({ type: "applyFilters" })}>
                  Apply
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        {!filtersOpen && !single ? (
          <footer className="tps-footer">
            <p className="text-xs tabular-nums shrink-0" style={{ color: "var(--color-text-secondary)" }} aria-live="polite">
              {summary.count} selected
              {summary.total > 0 ? <span style={{ color: "var(--color-text-muted)" }}> · {Math.round(summary.total).toLocaleString()}</span> : null}
              {atMax ? <span style={{ color: "var(--color-warning)" }}> · max</span> : null}
            </p>
            <Button fullWidth onClick={() => onApply(state.selected)}>
              {applyLabel(state.selected, initialSelected)}
            </Button>
          </footer>
        ) : null}
      </div>
    </div>
  );
  // Portaled: a fixed backdrop inside a transformed/filtered ancestor is positioned against it, not the viewport.
  return typeof document === "undefined" ? dialog : createPortal(dialog, document.body);
}

/** Open on Picks only when the side already holds picks and no players. */
function firstTab(items: SheetItem[], selected: string[]): "players" | "picks" {
  const kinds = selected.map((key) => items.find((i) => i.key === key)?.kind);
  return kinds.length > 0 && kinds.every((k) => k === "pick") ? "picks" : "players";
}

function FilterGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2" aria-label={title}>
      <h3 className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {title}
      </h3>
      <div className="flex flex-wrap gap-2">{children}</div>
    </section>
  );
}

function FilterChip({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button type="button" className="tps-filter-chip" aria-pressed={on} data-on={on ? "true" : "false"} onClick={onClick}>
      {label}
    </button>
  );
}

/** The row identity shared by every caller: avatar, position, name, team and age; picks use the pick row. */
function SheetItemIdentity({ item }: { item: SheetItem }) {
  if (item.kind === "pick") {
    return (
      <span className="flex min-w-0 flex-1 items-center gap-2">
        <span className="min-w-0 flex-1">
          <PickRow dense round={item.round} pickNo={item.pickNo} label={item.label} context={item.detail ?? null} />
        </span>
        {item.value != null ? <ValueStat value={Math.round(item.value).toLocaleString()} /> : null}
      </span>
    );
  }
  const meta = [item.team, item.age ? `Age ${item.age}` : null, item.detail].filter(Boolean).join(" · ") || "Player";
  return (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      <PlayerIdentity
        playerId={item.photoId ?? null}
        fallbackLabel={item.label.split(" ").map((w) => w[0]).slice(0, 2).join("")}
        name={item.label}
        position={item.position}
        tier={item.tier}
        injuryStatus={item.injury}
        avatarSize={36}
        disableQuickView
        className="min-w-0 flex-1"
      >
        {meta}
      </PlayerIdentity>
      {item.value != null ? <ValueStat value={Math.round(item.value).toLocaleString()} /> : null}
    </span>
  );
}

/**
 * The compact per-side summary shown on the trade page once the sheet is
 * closed: label, count and total value, the picked assets as removable chips,
 * and one big tap target (the whole header) that opens the sheet.
 */
export function TradeSideSummary({
  label,
  tone,
  items,
  onOpen,
  onRemove,
  hint,
  testId,
}: {
  label: string;
  tone: "danger" | "success";
  items: SheetItem[];
  onOpen: () => void;
  onRemove: (key: string) => void;
  hint?: string;
  testId?: string;
}) {
  const summary = summarizeItems(items);
  const color = tone === "danger" ? "var(--color-danger)" : "var(--color-success)";
  const parts = [summary.players ? `${summary.players} player${summary.players === 1 ? "" : "s"}` : "", summary.picks ? `${summary.picks} pick${summary.picks === 1 ? "" : "s"}` : ""].filter(Boolean).join(", ");
  return (
    <div className="glass-surface flex min-w-0 flex-col gap-1 p-2" data-testid={testId}>
      <button
        type="button"
        className="tps-side-open"
        aria-label={items.length ? `${label}: ${parts}. Edit` : `${label}: add players or picks`}
        onClick={onOpen}
      >
        <span className="flex min-w-0 flex-col items-start gap-0.5 text-left">
          <span className="flex items-center gap-1.5 text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            <span aria-hidden="true" className="inline-block" style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
            {label}
          </span>
          {items.length ? (
            <span className="text-sm font-extrabold tabular-nums">
              {parts}
              {summary.total > 0 ? <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}> · {Math.round(summary.total).toLocaleString()}</span> : null}
            </span>
          ) : (
            <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {hint ?? "Add players or picks"}
            </span>
          )}
        </span>
        <span className="tps-side-add" aria-hidden="true" style={{ color: "var(--color-accent)" }}>
          {items.length ? "Edit" : "+ Add"}
        </span>
      </button>
      {items.length ? (
        <ul className="tps-chips tps-side-chips" aria-label={`${label} assets`}>
          {items.map((item) => (
            <li key={item.key} className="tps-chip">
              {item.kind === "player" ? <PlayerName name={item.label} /> : <span className="truncate">{item.label}</span>}
              <button type="button" aria-label={`Remove ${item.label}`} onClick={() => onRemove(item.key)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
