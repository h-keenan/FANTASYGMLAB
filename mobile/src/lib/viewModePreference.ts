import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

export type PlayerListViewMode = 'list' | 'grid';

const KEY_PREFIX = 'fgl:player-list-view-mode:';

/**
 * Per-screen, per-device preference for the List <-> Grid toggle on the
 * dense player-list screens (Players, Waivers, College Prospects). Each
 * screen gets its own storage key (e.g. "players", "waivers") so choosing
 * Grid on one screen doesn't silently flip a different screen the user
 * never touched.
 *
 * Deliberately local-only (device AsyncStorage, no /v1/preferences sync like
 * DensityContext's uiDensity) — this is a lightweight display preference
 * for one list, not a cross-device account setting, and keeping it simple
 * avoids adding N new durable-preference fields for N screens. Best-effort,
 * same as every other AsyncStorage read/write in this codebase: a storage
 * failure just means the toggle doesn't remember itself next time, never a
 * crash or a blocked screen.
 *
 * Defaults to `'list'` (today's unchanged behavior) so a user who has never
 * touched the toggle sees exactly the existing full-width list — Grid is
 * opt-in, not a silent layout change.
 */
export function usePlayerListViewMode(screenKey: string): {
  viewMode: PlayerListViewMode;
  setViewMode: (mode: PlayerListViewMode) => void;
} {
  const storageKey = `${KEY_PREFIX}${screenKey}`;
  const [viewMode, setViewModeState] = useState<PlayerListViewMode>('list');

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(storageKey)
      .then((raw) => {
        if (cancelled) return;
        if (raw === 'list' || raw === 'grid') setViewModeState(raw);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [storageKey]);

  const setViewMode = useCallback(
    (mode: PlayerListViewMode) => {
      setViewModeState(mode);
      AsyncStorage.setItem(storageKey, mode).catch(() => {});
    },
    [storageKey],
  );

  return { viewMode, setViewMode };
}
