// Pure core of the in-app effects settings (Settings: "Haptics", "Reduced effects"). Storage is injected so the
// persistence rules are testable in node; `effectsPrefs.ts` binds AsyncStorage.

export type EffectsPrefs = { haptics: boolean; reducedEffects: boolean };
export const DEFAULT_EFFECTS_PREFS: EffectsPrefs = { haptics: true, reducedEffects: false };
export const EFFECTS_PREFS_KEY = 'fgl:effects-prefs:v1';

/** Tolerant parse: a missing, corrupt or partial value falls back to the defaults field by field. */
export function parseEffectsPrefs(raw: string | null | undefined): EffectsPrefs {
  if (!raw) return { ...DEFAULT_EFFECTS_PREFS };
  try {
    const v = JSON.parse(raw) as Partial<EffectsPrefs> | null;
    return {
      haptics: typeof v?.haptics === 'boolean' ? v.haptics : DEFAULT_EFFECTS_PREFS.haptics,
      reducedEffects: typeof v?.reducedEffects === 'boolean' ? v.reducedEffects : DEFAULT_EFFECTS_PREFS.reducedEffects,
    };
  } catch {
    return { ...DEFAULT_EFFECTS_PREFS };
  }
}

export type EffectsStorage = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<unknown>;
};

export function createEffectsPrefs(storage: EffectsStorage) {
  let state: EffectsPrefs = { ...DEFAULT_EFFECTS_PREFS };
  let touched = false;
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());
  return {
    get: () => state,
    subscribe(fn: () => void) {
      listeners.add(fn);
      return () => void listeners.delete(fn);
    },
    /** Reads the saved value once; a set() made before it finishes wins over the stale read. */
    async load() {
      try {
        const loaded = parseEffectsPrefs(await storage.getItem(EFFECTS_PREFS_KEY));
        if (!touched) {
          state = loaded;
          emit();
        }
      } catch {
        // Best effort: keep the defaults.
      }
    },
    set(patch: Partial<EffectsPrefs>) {
      touched = true;
      state = { ...state, ...patch };
      emit();
      void Promise.resolve(storage.setItem(EFFECTS_PREFS_KEY, JSON.stringify(state))).catch(() => undefined);
    },
  };
}
