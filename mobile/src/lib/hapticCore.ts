// Pure core of the haptic vocabulary (docs/design/app-motion-plan.md, section 2.4): the intent map, the throttle and
// the kill switch, with the native driver injected so it is testable in node. `haptic.ts` binds it to expo-haptics.

export type HapticIntent = 'tap' | 'select' | 'toggle' | 'commit' | 'lift' | 'drop' | 'snap' | 'success' | 'warn' | 'error' | 'epic';

export type HapticStep =
  | { kind: 'impact'; style: 'light' | 'medium' | 'rigid' | 'heavy' }
  | { kind: 'selection' }
  | { kind: 'notification'; type: 'success' | 'warning' | 'error' };

export type HapticPlan = readonly { step: HapticStep; delayMs: number }[];

const impact = (style: 'light' | 'medium' | 'rigid' | 'heavy'): HapticPlan => [{ step: { kind: 'impact', style }, delayMs: 0 }];
const notify = (type: 'success' | 'warning' | 'error'): HapticPlan => [{ step: { kind: 'notification', type }, delayMs: 0 }];

/** Every named intent and what it plays. Screens name an intent; they never pick a style. */
export const HAPTIC_INTENTS: Record<HapticIntent, HapticPlan> = {
  tap: impact('light'),
  select: [{ step: { kind: 'selection' }, delayMs: 0 }],
  toggle: impact('light'),
  commit: impact('medium'),
  lift: impact('medium'),
  drop: impact('light'),
  snap: impact('rigid'),
  success: notify('success'),
  warn: notify('warning'),
  error: notify('error'),
  epic: [
    { step: { kind: 'impact', style: 'heavy' }, delayMs: 0 },
    { step: { kind: 'notification', type: 'success' }, delayMs: 120 },
  ],
};

/** Minimum gap between two fires, so twenty ticking numbers or a fast scrub cannot buzz. */
export const HAPTIC_THROTTLE_MS = 60;

export type HapticDriver = (step: HapticStep) => Promise<unknown> | void;

export function createHaptics(opts: {
  driver: HapticDriver;
  isEnabled: () => boolean;
  now?: () => number;
  schedule?: (fn: () => void, ms: number) => void;
}): (intent: HapticIntent) => void {
  const now = opts.now ?? Date.now;
  const schedule = opts.schedule ?? ((fn, ms) => void setTimeout(fn, ms));
  let last = -Infinity;
  const play = (step: HapticStep) => {
    try {
      const out = opts.driver(step);
      if (out && typeof (out as Promise<unknown>).catch === 'function') (out as Promise<unknown>).catch(() => undefined);
    } catch {
      // Haptics are absent on simulators and some devices: never throw.
    }
  };
  return (intent) => {
    if (!opts.isEnabled()) return;
    const plan = HAPTIC_INTENTS[intent];
    if (!plan) return;
    const t = now();
    if (t - last < HAPTIC_THROTTLE_MS) return;
    last = t;
    for (const { step, delayMs } of plan) {
      if (delayMs <= 0) play(step);
      else schedule(() => (opts.isEnabled() ? play(step) : undefined), delayMs);
    }
  };
}
