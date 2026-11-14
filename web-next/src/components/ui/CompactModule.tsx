"use client";

import { useId, useState, useSyncExternalStore, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Sheet } from "@/components/ui/Sheet";
import { compactAriaLabel, compactParts, type CompactPart, type CompactTone } from "@/lib/compactModule";
import { simOpenKey, simParseOpen } from "@/lib/simLayout";

const OPEN_EVENT = "fgl:sim-open-change";

const TONE_COLOR: Record<CompactTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
  action: "var(--color-action)",
};

function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * THE compact module (docs/ui-patterns.md, "CompactModule"). One card for every dense block on every page, so a
 * page is a short stack of these instead of a wall of cards. Collapsed it is NOT an empty header: line 1 is the
 * title, line 2 (at most two lines) is a dense summary of the key numbers and status (`parts`), and an optional one
 * trailing `action` (a button such as "Draft Gibbs") works without expanding. Tapping the header expands the body
 * inline (default) or into a shared `Sheet` (`expandIn="sheet"`, for long bodies). The open state is remembered per
 * `id` unless `persist` is false. Mobile twin: mobile/src/components/CompactModule.tsx; logic: lib/compactModule.ts.
 */
export function CompactModule({
  id,
  title,
  label,
  parts,
  summary,
  tone = "accent",
  accent,
  action,
  defaultOpen = false,
  persist = true,
  expandIn = "inline",
  children,
  testId,
  glow = false,
}: {
  /** Stable key for remembering the open state, e.g. "draft.clock". */
  id: string;
  title: ReactNode;
  /** Plain-text name for screen readers and the sheet heading; defaults to `title` when it is a string. */
  label?: string;
  /** The collapsed summary: key numbers and status, in order. Empty parts are dropped; capped at six. */
  parts?: ReadonlyArray<CompactPart | null | undefined | false | "">;
  /** Legacy right-aligned node (used when there are no `parts`). Prefer `parts`. */
  summary?: ReactNode;
  tone?: CompactTone;
  /** CSS colour expression; defaults from `tone`. */
  accent?: string;
  /** One trailing primary action, usable while collapsed. */
  action?: ReactNode;
  defaultOpen?: boolean;
  persist?: boolean;
  expandIn?: "inline" | "sheet";
  children?: ReactNode;
  testId?: string;
  glow?: boolean;
}) {
  const key = simOpenKey(id);
  const bodyId = useId();
  const stored = useSyncExternalStore(
    (notify) => {
      window.addEventListener("storage", notify);
      window.addEventListener(OPEN_EVENT, notify);
      return () => {
        window.removeEventListener("storage", notify);
        window.removeEventListener(OPEN_EVENT, notify);
      };
    },
    () => (persist ? readStored(key) : null),
    () => null,
  );
  const [override, setOverride] = useState<boolean | null>(null);
  const open = override ?? simParseOpen(stored, defaultOpen);
  const shown = compactParts(parts ?? []);
  const name = label ?? (typeof title === "string" ? title : "Details");
  const hasBody = children != null && children !== false;

  function toggle() {
    const next = !open;
    setOverride(next);
    if (!persist || expandIn === "sheet") return;
    try {
      window.localStorage.setItem(key, next ? "1" : "0");
      window.dispatchEvent(new Event(OPEN_EVENT));
    } catch {
      /* storage blocked: the override keeps this session consistent */
    }
  }

  return (
    <AccentCard accent={accent ?? TONE_COLOR[tone]} as="section" compact glow={glow} className="min-w-0" data-testid={testId}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-expanded={hasBody ? open : undefined}
          aria-controls={hasBody && expandIn === "inline" ? bodyId : undefined}
          aria-label={compactAriaLabel(name, shown, open)}
          onClick={hasBody ? toggle : undefined}
          disabled={!hasBody}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          style={{ minHeight: "var(--touch-target-min)" }}
        >
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="flex items-center gap-2">
              <span className="shrink-0 whitespace-nowrap text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                {title}
              </span>
              {shown.length === 0 && summary ? <span className="min-w-0 flex-1 text-right">{summary}</span> : null}
            </span>
            {shown.length > 0 ? (
              <span className="text-sm leading-snug" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }} data-testid="compact-summary">
                {shown.map((part, i) => (
                  <span key={part.key}>
                    {i > 0 ? <span style={{ color: "var(--color-text-muted)" }}>{" · "}</span> : null}
                    <span style={{ color: part.tone ? TONE_COLOR[part.tone] : "var(--color-text-primary)", fontWeight: part.strong ? 800 : 600 }}>{part.text}</span>
                  </span>
                ))}
              </span>
            ) : null}
          </span>
          {hasBody ? (
            <span aria-hidden="true" className="shrink-0 text-xs" style={{ color: "var(--color-text-muted)", width: 12, textAlign: "center" }}>
              {open && expandIn === "inline" ? "−" : "+"}
            </span>
          ) : null}
        </button>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {expandIn === "inline" ? (
        <div id={bodyId} hidden={!open} className="flex flex-col gap-3 pt-1">
          {open ? children : null}
        </div>
      ) : (
        <Sheet open={open} onClose={() => setOverride(false)} title={name}>
          {children}
        </Sheet>
      )}
    </AccentCard>
  );
}
