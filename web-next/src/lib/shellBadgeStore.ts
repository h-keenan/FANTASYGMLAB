"use client";

import { useSyncExternalStore } from "react";

import type { MoreBadgeSources } from "@/lib/bottomNav";

/**
 * Sources of the shell's More badge. A page that already loaded the data (the Sim notification bell) publishes its counts
 * here; the bar reads them. Module-level like the pill store: no provider, no new request, no polling. A source is
 * cleared when its owner unmounts or its items are read.
 */
const sources = new Map<string, MoreBadgeSources>();
const listeners = new Set<() => void>();
let snapshot: MoreBadgeSources = {};

function recompute() {
  const next: MoreBadgeSources = {};
  for (const s of sources.values()) {
    next.waiverResults = (next.waiverResults ?? 0) + (s.waiverResults ?? 0);
    next.rosterInjuries = (next.rosterInjuries ?? 0) + (s.rosterInjuries ?? 0);
    next.simWeekReady = (next.simWeekReady ?? 0) + (s.simWeekReady ?? 0);
  }
  const same = JSON.stringify(next) === JSON.stringify(snapshot);
  if (same) return;
  snapshot = next;
  listeners.forEach((l) => l());
}

export function setShellBadges(source: string, counts: MoreBadgeSources | null) {
  if (counts) sources.set(source, counts);
  else sources.delete(source);
  recompute();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => void listeners.delete(l);
};
const EMPTY: MoreBadgeSources = {};

export function useShellBadges(): MoreBadgeSources {
  return useSyncExternalStore(subscribe, () => snapshot, () => EMPTY);
}
