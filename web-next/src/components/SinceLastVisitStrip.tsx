"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type HistoryTransaction } from "@/lib/api";
import {
  advanceLastVisit,
  buildSinceItems,
  lastVisitStorageKey,
  parseLastVisit,
  type SinceItem,
} from "@/lib/sinceLastVisit";

const TONE: Record<SinceItem["key"], string> = {
  trades: "var(--color-accent)",
  claims: "var(--color-opportunity)",
  news: "var(--color-warning)",
};

function readState(key: string) {
  try {
    return parseLastVisit(window.localStorage.getItem(key));
  } catch {
    return null;
  }
}

function writeState(key: string, state: { since: number; last: number }) {
  try {
    window.localStorage.setItem(key, JSON.stringify(state));
  } catch {
    // Best effort: worst case the strip is empty next time.
  }
}

/**
 * Dashboard "Since your last visit" strip (web twin of the app's "Since your
 * last check-in"). Real data only: new trades and waiver activity in the
 * league (GET .../history) after the stored last-visit time. News and
 * injuries on rostered players are not repeated here: they live once, in
 * Watchlist & Alerts. Renders nothing on a first
 * visit, when nothing changed, or when either request fails. The two reads
 * start only for a returning visitor, after the Dashboard has painted.
 */
export function SinceLastVisitStrip({
  userId,
  leagueId,
  leagueName,
}: {
  userId: string;
  leagueId: string;
  leagueName: string;
}) {
  const [items, setItems] = useState<SinceItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    const key = lastVisitStorageKey(userId, leagueId);
    const { next, display } = advanceLastVisit(readState(key), Date.now());
    writeState(key, next);
    if (display == null) return;

    const settled = Promise.allSettled([api.getLeagueHistory(leagueId)]);
    void settled.then(([history]) => {
      if (cancelled) return;
      const transactions: HistoryTransaction[] = history.status === "fulfilled" ? history.value.transactions ?? [] : [];
      setItems(buildSinceItems({ transactions, alerts: [], sinceMs: display }));
    });
    return () => {
      cancelled = true;
    };
  }, [userId, leagueId]);

  if (items.length === 0) return null;
  const query = `?name=${encodeURIComponent(leagueName)}`;
  return (
    <section aria-label="Since your last visit" data-testid="since-last-visit" className="flex flex-col gap-2">
      <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
        Since your last visit
      </span>
      <div className="grid grid-cols-2 gap-2 [&>*:last-child:nth-child(odd)]:col-span-2">
        {items.map((item) => (
          <Link
            key={item.key}
            href={`/${item.segment}/${encodeURIComponent(leagueId)}${query}`}
            className="glass-surface flex flex-col px-3 py-2"
            style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}
          >
            <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
              {item.label}
            </span>
            <span className="text-sm font-bold" style={{ color: TONE[item.key] }}>
              {item.value}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
