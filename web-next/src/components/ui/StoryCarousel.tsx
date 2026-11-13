"use client";

import { useCallback, useEffect, useReducer, useRef, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { OverlayBack } from "@/components/OverlayBack";
import { useOverlay } from "@/lib/useOverlay";
import { storyInitial, storyIsLast, storyKeyAction, storyReducer, storySegmentFill, storySwipeAction, storyTapAction } from "@/lib/storyCarousel";

import "./ui.css";

export interface StoryPage {
  key: string;
  /** Short kicker above the page ("Result", "Around the league"). */
  label: string;
  /** The page itself: a hero number and at most three supporting items. No scrolling. */
  content: ReactNode;
  /** Page footer (a CTA). The last page's footer is the story's finish action. */
  footer?: ReactNode;
}

/**
 * The shared full-screen story carousel (Instagram-stories style): one glanceable page at a time, page
 * progress segments on top, a close X, swipe or tap the left/right of the screen or use the arrow keys.
 * Used by the Fantasy Sim weekly recap; built to be reused for any "story" moment (season recap, draft
 * recap, offseason review): hand it `pages`. See docs/ui-patterns.md.
 *
 * Rules it follows: portaled to <body> as a dialog (focus in on open, back to the trigger on close), registered
 * with the overlay stack (useOverlay): one pop-up at a time, so a player card opened from a page replaces the
 * story (kept mounted, hidden) and its "Back" returns to the same page; the X closes everything, Escape and
 * browser Back go back one step; the stack owns the scroll lock, history and the z-index. Safe-area aware, a
 * short slide animation that is off under reduced motion. Taps on buttons, links or
 * anything marked `data-story-interactive` never flip the page.
 */
export function StoryCarousel({
  title,
  pages,
  onClose,
  initialIndex = 0,
  testId = "story-carousel",
}: {
  title: string;
  pages: StoryPage[];
  onClose: () => void;
  initialIndex?: number;
  testId?: string;
}) {
  const [state, dispatch] = useReducer(storyReducer, undefined, () => storyInitial(pages.length, initialIndex));
  const rootRef = useRef<HTMLDivElement>(null);
  const pointer = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    dispatch({ type: "count", count: pages.length });
  }, [pages.length]);

  // THE overlay stack decides visibility, back-stack, browser history, the one scroll lock and layering
  // (lib/overlayStack.ts): a player card opened from a page replaces the story (it stays mounted, hidden) and
  // its Back returns here on the same page.
  const overlay = useOverlay({ title, onClose });
  const hidden = overlay.hidden;
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    return () => previousFocus?.focus?.({ preventScroll: true });
  }, []);
  useEffect(() => {
    if (!hidden) rootRef.current?.focus({ preventScroll: true });
  }, [hidden]);

  const next = useCallback(() => (storyIsLast(state) ? overlay.closeAll() : dispatch({ type: "next" })), [state, overlay]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const action = storyKeyAction(event.key);
    if (!action) return;
    event.preventDefault();
    event.stopPropagation();
    if (action === "close") overlay.back();
    else if (action === "next") dispatch({ type: "next" });
    else dispatch({ type: "prev" });
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    pointer.current = { x: event.clientX, y: event.clientY };
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    const start = pointer.current;
    pointer.current = null;
    if (!start) return;
    const swipe = storySwipeAction(event.clientX - start.x, event.clientY - start.y);
    if (swipe) {
      dispatch({ type: swipe });
      return;
    }
    const target = event.target as HTMLElement;
    if (target.closest("button, a, input, select, textarea, [data-story-interactive]")) return;
    if (Math.abs(event.clientX - start.x) > 10 || Math.abs(event.clientY - start.y) > 10) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const zone = storyTapAction(event.clientX - rect.left, rect.width);
    if (zone === "prev") dispatch({ type: "prev" });
    else if (!storyIsLast(state)) dispatch({ type: "next" });
  }

  const page = pages[Math.min(state.index, pages.length - 1)];
  if (!page) return null;
  const last = storyIsLast(state);

  const dialog = (
    <div
      ref={rootRef}
      className="ui-story"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabIndex={-1}
      data-testid={testId}
      hidden={hidden}
      style={{ zIndex: overlay.zIndex }}
      onKeyDown={onKeyDown}
    >
      <div className="ui-story-top">
        <OverlayBack overlay={overlay} />
        <div className="ui-story-progress" role="progressbar" aria-label={`Page ${state.index + 1} of ${state.count}`} aria-valuemin={1} aria-valuemax={state.count} aria-valuenow={state.index + 1}>
          {pages.map((p, i) => (
            <button key={p.key} type="button" className="ui-story-seg" data-fill={storySegmentFill(i, state.index)} aria-label={`Go to ${p.label}`} onClick={() => dispatch({ type: "goto", index: i })}>
              <span />
            </button>
          ))}
        </div>
        <button type="button" className="ui-story-close" aria-label={`Close ${title}`} onClick={overlay.closeAll}>
          <span aria-hidden="true">×</span>
        </button>
      </div>
      <p className="ui-story-kicker">{page.label}</p>
      <div className="ui-story-stage" onPointerDown={onPointerDown} onPointerUp={onPointerUp} onPointerCancel={() => (pointer.current = null)} data-testid="story-stage">
        <div key={page.key} className="ui-story-page" data-dir={state.direction} data-testid={`story-page-${page.key}`} aria-live="polite">
          {page.content}
        </div>
        {state.index > 0 ? (
          <button type="button" className="ui-story-nav" data-side="prev" aria-label="Previous page" onClick={() => dispatch({ type: "prev" })}>
            ‹
          </button>
        ) : null}
        {!last ? (
          <button type="button" className="ui-story-nav" data-side="next" aria-label="Next page" onClick={next}>
            ›
          </button>
        ) : null}
      </div>
      {page.footer ? <div className="ui-story-foot">{page.footer}</div> : null}
    </div>
  );
  return typeof document === "undefined" ? dialog : createPortal(dialog, document.body);
}
