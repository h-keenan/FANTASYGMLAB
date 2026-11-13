"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import {
  feedAgeLabel,
  feedPointsLabel,
  groupFeedByGame,
  liveFeedStore,
  type FeedEvent,
} from "@/lib/liveFeed";

/**
 * Collapsible "Live feed": scoring events derived by diffing polled snapshots
 * while this page is open (lib/liveFeed.ts). Latest first, grouped by NFL game,
 * no auto-scroll, "NEW" on items arrived since the panel was last closed, at
 * most 50 kept, held in memory per matchup. Items are stamped with the poll
 * time and marked "approx." when several things merged. Not play-by-play.
 */
export function LiveFeedPanel({ feedKey, live }: { feedKey: string; live: boolean }) {
  const events = useSyncExternalStore(
    liveFeedStore.subscribe,
    () => liveFeedStore.events(feedKey),
    () => liveFeedStore.events(feedKey),
  );
  const [open, setOpen] = useState(false);
  const [seenAt, setSeenAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!open) return;
    const timer = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(timer);
  }, [open]);

  if (events.length === 0 && !live) return null;
  const unseen = events.filter((event) => event.at > seenAt).length;
  const groups = groupFeedByGame(events, liveFeedStore.snapshot(feedKey));
  const toggle = () => {
    if (open) setSeenAt(Date.now()); // closing marks everything seen
    else setNow(Date.now());
    setOpen((value) => !value);
  };

  return (
    <section className="glass-surface flex flex-col gap-2 p-4" aria-labelledby="live-feed-title" data-testid="live-feed">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls="live-feed-body"
        className="flex items-center justify-between gap-3 w-full text-left"
      >
        <span className="flex items-center gap-2">
          <h2 id="live-feed-title" className="m-0 text-sm font-extrabold uppercase" style={{ letterSpacing: "var(--letter-spacing-badge)", color: "var(--color-text-primary)" }}>
            Live feed
          </h2>
          {live ? <ToneBadge size="xs" label="● LIVE" color="var(--color-success)" /> : null}
          {!open && unseen > 0 ? <ToneBadge size="xs" testId="live-feed-new-count" label={`${unseen} new`} color="var(--color-accent)" /> : null}
        </span>
        <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
          {open ? "Hide" : `Show${events.length ? ` (${events.length})` : ""}`}
        </span>
      </button>
      {open ? (
        <div id="live-feed-body" className="flex flex-col gap-3" role="log" aria-live="polite" aria-label="Scoring updates">
          {events.length === 0 ? (
            <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
              Scoring changes appear here as they happen while this page is open.
            </p>
          ) : (
            groups.map((game) => (
              <div key={game.key} className="flex flex-col gap-1.5" data-testid="live-feed-game">
                <div className="flex items-center gap-2 text-[11px] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                  <span>{game.label}</span>
                  {game.status ? <span style={{ color: "var(--color-text-secondary)" }}>{game.status}</span> : null}
                </div>
                <ul className="flex flex-col gap-1.5 list-none p-0 m-0">
                  {game.events.map((event) => (
                    <FeedItem key={event.id} event={event} now={now} isNew={event.at > seenAt} />
                  ))}
                </ul>
              </div>
            ))
          )}
          <p className="m-0 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
            Built from score changes between refreshes, so times are when we noticed (not the play clock) and busy drives may be combined (&ldquo;approx.&rdquo;).
          </p>
        </div>
      ) : null}
    </section>
  );
}

function FeedItem({ event, now, isNew }: { event: FeedEvent; now: number; isNew: boolean }) {
  const tone = event.points < 0 ? "var(--color-danger)" : "var(--color-success)";
  return (
    <li
      className="flex items-center gap-2 px-2.5 py-1.5 min-w-0"
      style={{
        borderRadius: "var(--radius-md)",
        background: "var(--glass-input-bg)",
        border: "1px solid var(--glass-input-border)",
        boxShadow: event.side === "mine" ? "inset 3px 0 0 var(--color-accent)" : "inset 3px 0 0 var(--color-border-strong)",
      }}
      data-testid="live-feed-item"
    >
      <PositionBadge position={event.position} />
      <span className="flex flex-col min-w-0 flex-1">
        <span className="flex items-baseline gap-1.5 min-w-0">
          <span className="text-[13px] font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
            {event.name}
          </span>
          <span className="text-[13px] font-extrabold tabular-nums shrink-0" style={{ color: tone }}>
            {feedPointsLabel(event.points)}
          </span>
        </span>
        <span className="text-[11px]" style={{ color: "var(--color-text-secondary)" }}>
          {event.detail}
          {event.approx ? " · approx." : ""}
        </span>
      </span>
      <span className="flex flex-col items-end shrink-0 gap-0.5">
        <span className="text-[10px]" style={{ color: "var(--color-text-muted)" }}>
          {feedAgeLabel(event.at, now)}
        </span>
        <span className="text-[10px] font-bold uppercase" style={{ color: event.side === "mine" ? "var(--color-accent)" : "var(--color-text-muted)" }}>
          {event.side === "mine" ? "You" : "Opp"}
        </span>
        {isNew ? <ToneBadge size="xs" label="NEW" color="var(--color-accent)" /> : null}
      </span>
    </li>
  );
}
