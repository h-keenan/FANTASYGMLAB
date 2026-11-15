"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from "react";

import {
  collapseTargetPx,
  dropPresenceEntry,
  mergePresenceEntries,
  shouldAnimatePresenceList,
  type PresenceEntry,
  type PresenceVariant,
} from "@/lib/presence";
import { usePresence } from "@/lib/usePresence";
import { easeCss } from "@/lib/motion";

/**
 * THE appear / disappear primitive (docs/ui-patterns.md "Presence"). Anything that shows or hides (a toast, a banner, an
 * expander body, a list row, a swapped body) goes through this instead of `cond && <X />`, so nothing pops. It mounts on
 * `show`, animates in, and on hide animates out and only then unmounts, keeping the last children on screen while it
 * leaves. Opacity, transform and (variant "collapse") a measured height only; 120-300ms; under prefers-reduced-motion it
 * simply appears and disappears. Rules and durations: lib/presence.ts; hook: lib/usePresence.ts; app twin:
 * mobile/src/components/Presence.tsx.
 *
 * Variants: "fade" (opacity), "rise" (+ a short lift: toasts, banners), "pop" (+ a small scale), "collapse" (height + opacity:
 * expander bodies, list rows). `appear` animates in when already shown on first render. The wrapper is a plain div (`as`
 * to change it); do not put a `position: fixed` child under a transformed variant, give the wrapper itself the fixed class.
 */
export function Presence({
  show,
  variant = "fade",
  appear = false,
  enterMs,
  exitMs,
  onExited,
  as,
  className,
  style,
  testId,
  children,
  ...aria
}: {
  show: boolean;
  variant?: PresenceVariant;
  appear?: boolean;
  enterMs?: number;
  exitMs?: number;
  onExited?: () => void;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
  testId?: string;
  children?: ReactNode;
  id?: string;
  role?: string;
  "aria-live"?: "polite" | "assertive" | "off";
  "aria-hidden"?: boolean;
}) {
  const Tag: ElementType = as ?? "div";
  const state = usePresence(show, { enterMs, exitMs, appear, onExited });
  // Keep the last shown children so the exit has something to play on after the caller stops rendering them.
  const [kept, setKept] = useState<ReactNode>(children);
  if (show && kept !== children) setKept(children);
  const ref = useRef<HTMLElement | null>(null);
  const leaving = useRef(false);
  const { phase, enterMs: enterFor, exitMs: exitFor } = state;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || variant !== "collapse") return;
    const clear = () => {
      el.style.height = "";
      el.style.overflow = "";
      el.style.opacity = "";
      el.style.transition = "";
    };
    if (phase === "entering") {
      const from = leaving.current ? el.getBoundingClientRect().height : 0;
      leaving.current = false;
      el.style.transition = "none";
      el.style.overflow = "hidden";
      el.style.height = `${from}px`;
      el.style.opacity = from > 0 ? "1" : "0";
      el.style.height = "auto";
      const to = collapseTargetPx(el.scrollHeight);
      el.style.height = `${from}px`;
      void el.offsetHeight; // commit the start frame before transitioning
      el.style.transition = `height ${enterFor}ms ${easeCss("out")}, opacity ${enterFor}ms ${easeCss("out")}`;
      el.style.height = to === null ? "auto" : `${to}px`;
      el.style.opacity = "1";
    } else if (phase === "exiting") {
      leaving.current = true;
      const from = el.getBoundingClientRect().height;
      el.style.transition = "none";
      el.style.overflow = "hidden";
      el.style.height = `${from}px`;
      void el.offsetHeight;
      el.style.transition = `height ${exitFor}ms ${easeCss("in")}, opacity ${exitFor}ms ${easeCss("in")}`;
      el.style.height = "0px";
      el.style.opacity = "0";
    } else {
      leaving.current = false;
      clear();
    }
  }, [phase, variant, enterFor, exitFor]);

  if (!state.mounted) return null;
  return (
    <Tag
      ref={ref}
      className={`presence presence-${variant}${className ? ` ${className}` : ""}`}
      data-presence={phase}
      data-variant={variant}
      data-testid={testId}
      style={{ "--presence-enter": `${enterFor}ms`, "--presence-exit": `${exitFor}ms`, ...style } as CSSProperties}
      {...aria}
    >
      {show ? children : kept}
    </Tag>
  );
}

/** An expander body: `<Collapse open={open}>…</Collapse>` replaces `{open ? <div>…</div> : null}`. Height + opacity, measured. */
export function Collapse({
  open,
  appear = false,
  className,
  testId,
  children,
  ...rest
}: {
  open: boolean;
  appear?: boolean;
  className?: string;
  testId?: string;
  children?: ReactNode;
  id?: string;
  role?: string;
  "aria-hidden"?: boolean;
}) {
  return (
    <Presence show={open} variant="collapse" appear={appear} className={className} testId={testId} {...rest}>
      {children}
    </Presence>
  );
}

/**
 * Rows that are added and removed: a row leaving plays its exit in the place it was, then goes; a new row enters. Lists
 * longer than 24 rows do not animate (they stay instant). `render` gets the item and its index among the CURRENT items.
 */
export function PresenceList<T>({
  items,
  getKey,
  render,
  variant = "collapse",
  appear = false,
  rowClassName,
  as,
}: {
  items: readonly T[];
  getKey: (item: T) => string;
  render: (item: T, index: number) => ReactNode;
  variant?: PresenceVariant;
  /** Animate the rows already present on first render (default: they are simply there). */
  appear?: boolean;
  rowClassName?: string;
  as?: ElementType;
}) {
  const [entries, setEntries] = useState<PresenceEntry<T>[]>(() => items.map((item) => ({ key: getKey(item), item, present: true })));
  // Rows that were there on first render are simply there; a row added later enters.
  const [initialKeys] = useState(() => new Set(items.map(getKey)));
  const animate = shouldAnimatePresenceList(items.length);
  const merged = mergePresenceEntries(entries, items, getKey);
  // Settle `entries` to the merge during render (no stale frame); rows that are gone drop out when their exit has played.
  const same = merged.length === entries.length && merged.every((m, i) => m.key === entries[i].key && m.present === entries[i].present && m.item === entries[i].item);
  if (!same) setEntries(animate ? merged : merged.filter((m) => m.present));
  const visible = animate ? merged : merged.filter((m) => m.present);
  const presentKeys = visible.filter((entry) => entry.present).map((entry) => entry.key);
  return (
    <>
      {visible.map((entry) => {
        return (
          <Presence
            key={entry.key}
            show={entry.present}
            variant={variant}
            appear={appear || !initialKeys.has(entry.key)}
            as={as}
            className={rowClassName}
            onExited={() => setEntries((prev) => dropPresenceEntry(prev, entry.key))}
          >
            {render(entry.item, Math.max(0, presentKeys.indexOf(entry.key)))}
          </Presence>
        );
      })}
    </>
  );
}

/**
 * A body that is replaced when `swapKey` changes (a sheet's tab content, a stepper's page): the old one fades out, then the
 * new one rises in, instead of one frame swapping them. Same key = it just re-renders. Reduced motion: an instant swap.
 */
export function PresenceSwap({ swapKey, children, className }: { swapKey: string; children: ReactNode; className?: string }) {
  const [shown, setShown] = useState<{ key: string; node: ReactNode }>({ key: swapKey, node: children });
  if (shown.key === swapKey && shown.node !== children) setShown({ key: swapKey, node: children });
  const incoming = shown.key !== swapKey;
  return (
    <Presence
      show={!incoming}
      variant="rise"
      className={className}
      onExited={() => {
        // The old body has left: bring the new one in.
        setShown({ key: swapKey, node: children });
      }}
    >
      {shown.node}
    </Presence>
  );
}
