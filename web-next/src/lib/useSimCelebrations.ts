"use client";

import { useCallback, useSyncExternalStore } from "react";

import { SIM_CELEBRATIONS_KEY, simCelebrationsParse, simCelebrationsSerialize } from "@/lib/simMoments";

const EVENT = "fd-sim-celebrations";

function read(): boolean {
  try {
    return simCelebrationsParse(window.localStorage.getItem(SIM_CELEBRATIONS_KEY));
  } catch {
    return true; // storage blocked: the setting is on, like its default
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** The Celebrations setting (pick reveals, score roll-ins, win and loss stamps, streak badges). On by default; per device. */
export function useSimCelebrations(): [boolean, (on: boolean) => void] {
  const on = useSyncExternalStore(subscribe, read, () => true);
  const set = useCallback((next: boolean) => {
    try {
      window.localStorage.setItem(SIM_CELEBRATIONS_KEY, simCelebrationsSerialize(next));
    } catch {
      // Storage is blocked: the change lasts until reload.
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [on, set];
}
