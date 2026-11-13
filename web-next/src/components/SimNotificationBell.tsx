"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { PulseOnIncrease } from "@/components/Motion";
import type { SimCtx } from "@/components/SimGameParts";
import { SIM_ICON_BTN, SIM_ICON_STYLE } from "@/components/SimGameHeader";
import { SimGlyph } from "@/components/SimGlyph";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import type { SimGlyphName } from "@/lib/simGame";
import {
  simNotifBadge,
  simNotifCursorKey,
  simNotifGroups,
  simNotifKey,
  simNotifMarkAllRead,
  simNotifParseCursor,
  simNotifTargetTab,
  simNotifTime,
  simNotifUnread,
  type SimNotifTab,
  type SimNotification,
} from "@/lib/simNotifications";

function readCursor(gameId: string): number {
  if (typeof window === "undefined") return 0;
  try {
    return simNotifParseCursor(window.localStorage.getItem(simNotifCursorKey(gameId)));
  } catch {
    return 0;
  }
}

function writeCursor(gameId: string, value: number) {
  try {
    window.localStorage.setItem(simNotifCursorKey(gameId), String(value));
  } catch {
    /* private window: the cursor lives only in memory this session */
  }
}

/**
 * The bell's data: ONE request (GET /games/{id}/notifications), refetched only when the game changed
 * (simNotifKey: week, phase, inbox, lineup warnings, claims, tick), never on a timer. The read cursor is a number in
 * localStorage per game; the unread count is computed against it locally.
 */
export function useSimNotifications(ctx: SimCtx) {
  const { gameId, game } = ctx;
  const [items, setItems] = useState<SimNotification[]>([]);
  const [latest, setLatest] = useState(0);
  // The cursor is state keyed by game (read from storage on first use per game, no effect needed).
  const [cursorState, setCursorState] = useState<{ id: string; value: number }>(() => ({ id: gameId, value: readCursor(gameId) }));
  const cursor = cursorState.id === gameId ? cursorState.value : readCursor(gameId);
  const key = simNotifKey(game, ctx.tick);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve(api.getSimNotifications?.(gameId, readCursor(gameId)))
      .then((body) => {
        if (!body) return;
        if (cancelled || body.reason) return;
        setItems(body.items ?? []);
        setLatest(body.seq ?? 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, key]);

  const unread = useMemo(() => simNotifUnread(items, cursor), [items, cursor]);
  const markAllRead = useCallback(() => {
    const next = simNotifMarkAllRead(cursor, latest);
    setCursorState({ id: gameId, value: next });
    writeCursor(gameId, next);
  }, [cursor, latest, gameId]);
  return { items, unread, cursor, markAllRead };
}

/** The header bell: unread badge (pulses on a new one) and the notification sheet. Mobile twin: components/SimNotificationBell.tsx. */
export function SimNotificationBell({ notif, onOpenTab }: { notif: ReturnType<typeof useSimNotifications>; onOpenTab: (tab: SimNotifTab) => void }) {
  const { items, unread, cursor, markAllRead } = notif;
  const [open, setOpen] = useState(false);
  const groups = useMemo(() => simNotifGroups(items), [items]);
  // Opening marks everything read, but the rows keep their "new" dot for this view (cursor at open time).
  const [seenCursor, setSeenCursor] = useState(0);

  function openSheet() {
    setSeenCursor(cursor);
    setOpen(true);
    markAllRead();
  }

  function go(item: SimNotification) {
    setOpen(false);
    onOpenTab(simNotifTargetTab(item.target));
  }

  const badge = simNotifBadge(unread);
  return (
    <>
      <button
        type="button"
        className={`relative ${SIM_ICON_BTN}`}
        style={SIM_ICON_STYLE}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        onClick={openSheet}
        data-testid="sim-bell"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7" />
          <path d="M10 20a2 2 0 0 0 4 0" />
        </svg>
        {badge ? (
          <span className="absolute -right-1 -top-1" data-testid="sim-bell-badge">
            <PulseOnIncrease value={unread}>
              <span className="inline-flex items-center justify-center text-[0.625rem] font-extrabold leading-none" style={{ minWidth: 18, height: 18, padding: "0 5px", borderRadius: "var(--radius-pill)", background: "var(--color-accent)", color: "var(--color-on-accent)" }}>
                {badge}
              </span>
            </PulseOnIncrease>
          </span>
        ) : null}
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title="Notifications" description="What happened in your game." testId="sim-notifications">
        {items.length === 0 ? (
          <p className="py-6 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>Nothing yet. Offers, claims, injuries and recaps land here.</p>
        ) : (
          <div className="flex flex-col gap-3" data-testid="sim-notification-list">
            <div className="flex justify-end">
              <Button size="sm" variant="ghost" disabled={unread === 0 && cursor >= seenCursor} onClick={markAllRead}>Mark all read</Button>
            </div>
            {groups.map((group) => (
              <section key={group.week} aria-label={group.label} className="flex flex-col">
                <h3 className="pb-1 text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{group.label}</h3>
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="flex items-center gap-3 text-left"
                    style={{ minHeight: 56, borderTop: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)" }}
                    onClick={() => go(item)}
                    data-unread={item.seq > seenCursor ? "true" : undefined}
                  >
                    <span className="inline-grid shrink-0 place-items-center rounded-full" style={{ width: 36, height: 36, background: "var(--glass-input-bg)", color: "var(--color-accent)" }}>
                      <SimGlyph name={item.icon as SimGlyphName} size={18} />
                    </span>
                    <span className="min-w-0 flex-1 text-sm font-semibold" style={{ fontWeight: item.seq > seenCursor ? 800 : 600 }}>{item.headline}</span>
                    <span className="shrink-0 text-xs" style={{ color: "var(--color-text-muted)" }}>{simNotifTime(item)}</span>
                    {item.seq > seenCursor ? <span aria-label="New" className="shrink-0 rounded-full" style={{ width: 8, height: 8, background: "var(--color-accent)" }} /> : null}
                  </button>
                ))}
              </section>
            ))}
          </div>
        )}
      </Sheet>
    </>
  );
}
