"use client";

import { useEffect, useSyncExternalStore } from "react";

import { firstRunPromptSlot, type FirstRunPrompt } from "./firstRunFlow.ts";

/**
 * Registers whether a first-run prompt wants Today's one prompt slot and says whether it won
 * (see firstRunPromptSlot in firstRunFlow.ts). The store is module-level so the three cards
 * stay independent components; a prompt that unmounts releases its claim. Twin: mobile useFirstRunPrompt.
 *
 *   const mayShow = useFirstRunPrompt("start_here", wantsToShow);   // call before any early return
 *   if (!wantsToShow || !mayShow) return null;
 */
const wants: Partial<Record<FirstRunPrompt, boolean>> = {};
const listeners = new Set<() => void>();
let winner: FirstRunPrompt | null = null;

export function claimFirstRunPrompt(kind: FirstRunPrompt, want: boolean): void {
  if ((wants[kind] === true) === want) return;
  wants[kind] = want;
  const next = firstRunPromptSlot(wants);
  if (next === winner) return;
  winner = next;
  listeners.forEach((listener) => listener());
}

export function currentFirstRunPrompt(): FirstRunPrompt | null {
  return winner;
}

/** Test helper: forget every claim. */
export function resetFirstRunPrompts(): void {
  for (const key of Object.keys(wants)) delete wants[key as FirstRunPrompt];
  winner = null;
  listeners.forEach((listener) => listener());
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

export function useFirstRunPrompt(kind: FirstRunPrompt, want: boolean): boolean {
  useEffect(() => {
    claimFirstRunPrompt(kind, want);
    return () => claimFirstRunPrompt(kind, false);
  }, [kind, want]);
  const current = useSyncExternalStore(subscribe, currentFirstRunPrompt, () => null);
  return want && current === kind;
}
