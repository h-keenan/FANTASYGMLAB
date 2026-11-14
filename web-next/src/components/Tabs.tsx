"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";

import { PillRow } from "@/components/PillRow";
import { readSavedTab, resolveTab, saveTab, tabDirection } from "@/lib/sessionTab";
import { nextPanelMinHeight } from "@/lib/sheetTabs";
import type { TabIconName } from "@/lib/tabIcons";

export interface TabItem {
  key: string;
  label: string;
  glyph?: TabIconName;
  /** Small count pill beside the label. */
  count?: number;
  /** Rendered only while this tab is open (panels are lazy, so a heavy tab costs nothing until it is picked). */
  render: () => ReactNode;
}

function sessionStore(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

/**
 * THE tabs for a surface that has more to say than one screen (player sheet, team sheet): the shared tab strip
 * (PillRow, in its slim in-sheet look) over lazily rendered panels. Built on the existing control, not beside it, so
 * keyboard (arrows / Home / End), the sliding underline and glass tokens are the same everywhere. Adds what a tabbed
 * surface needs: a tabpanel wired to its tab, a short slide-in from the side you moved toward (off under
 * prefers-reduced-motion) and the last tab remembered for the session under `id` (mobile twin: components/Tabs.tsx).
 */
export function Tabs({
  id,
  tabs,
  initial,
  ariaLabel,
  onChange,
  sticky = true,
}: {
  /** Stable name of the surface ("pqv", "sim-team"); the remembered tab is stored under it. */
  id: string;
  tabs: readonly TabItem[];
  initial?: string;
  ariaLabel?: string;
  onChange?: (key: string) => void;
  /** Pin the tab strip to the top of the sheet's scroll area (default). Off only where nothing scrolls. */
  sticky?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const keys = tabs.map((t) => t.key);
  const [active, setActive] = useState(() => resolveTab(readSavedTab(sessionStore(), id), keys, initial));
  const previous = useRef(active);
  const [dir, setDir] = useState<-1 | 0 | 1>(0);
  // A remembered tab that no longer exists (a tab hidden for this player) falls back instead of rendering nothing.
  const current = keys.includes(active) ? active : resolveTab(null, keys, initial);

  function select(key: string) {
    setDir(tabDirection(keys, previous.current, key));
    previous.current = key;
    setActive(key);
    saveTab(sessionStore(), id, key);
    onChange?.(key);
  }

  useEffect(() => {
    previous.current = current;
  }, [current]);

  // No layout jump between tabs: the panel keeps the tallest height this open sheet has shown as its minimum, so a
  // short tab after a long one does not pull the sheet (and the strip) up under the finger.
  const panelRef = useRef<HTMLDivElement>(null);
  const [minHeight, setMinHeight] = useState(0);
  useLayoutEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const measured = el.scrollHeight;
    setMinHeight((prev) => {
      const next = nextPanelMinHeight(prev, measured);
      return next === prev ? prev : next;
    });
  });

  const tab = tabs.find((t) => t.key === current);
  return (
    <div className="flex flex-col gap-3" data-testid="tabs">
      <div className={sticky ? "tabs-sticky" : undefined} data-sticky={sticky ? "true" : undefined}>
      <PillRow
        slim
        variant="scroll"
        ariaLabel={ariaLabel}
        tabIdPrefix={`${id}-${uid}`}
        options={tabs.map((t) => ({ label: t.label, value: t.key, glyph: t.glyph, count: t.count }))}
        active={current}
        onSelect={select}
      />
      </div>
      <div
        key={current}
        ref={panelRef}
        style={minHeight > 0 ? { minHeight } : undefined}
        role="tabpanel"
        id={`${id}-${uid}-panel-${current}`}
        aria-labelledby={`${id}-${uid}-tab-${current}`}
        className="tabs-panel flex min-w-0 flex-col gap-4"
        data-dir={dir === 0 ? undefined : dir}
        tabIndex={-1}
      >
        {tab ? tab.render() : null}
      </div>
    </div>
  );
}
