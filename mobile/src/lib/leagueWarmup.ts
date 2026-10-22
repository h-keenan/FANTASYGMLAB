export type WarmupStages = { roster: boolean; values: boolean; trades: boolean };

export type WarmupStatus = {
  ok: boolean;
  state: 'none' | 'running' | 'done' | 'error';
  stages: WarmupStages;
};

export const WARMUP_STEPS: { key: keyof WarmupStages; label: string }[] = [
  { key: 'roster', label: 'Reading your roster' },
  { key: 'values', label: 'Valuing your players' },
  { key: 'trades', label: 'Building trade ideas' },
];

/**
 * Follows the server's real warm-up progress for a just-saved league
 * (GET /v1/leagues/{id}/warmup-status). No timers stand in for progress:
 * `onUpdate` only ever sees what the server reported. Calls `onDone` exactly
 * once when the league is warm ("none"), finished, failed, the request
 * fails, or `maxPolls` is reached (the Dashboard then loads what is left
 * itself). Returns a cancel function.
 */
export function followLeagueWarmup(
  fetchStatus: () => Promise<WarmupStatus>,
  handlers: { onUpdate: (status: WarmupStatus) => void; onDone: () => void },
  options: { intervalMs?: number; maxPolls?: number } = {},
): () => void {
  const intervalMs = options.intervalMs ?? 800;
  const maxPolls = options.maxPolls ?? 40;
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let polls = 0;

  const finish = () => {
    if (!cancelled) {
      cancelled = true;
      handlers.onDone();
    }
  };

  const poll = async () => {
    polls += 1;
    try {
      const status = await fetchStatus();
      if (cancelled) return;
      handlers.onUpdate(status);
      if (status.state !== 'running' || polls >= maxPolls) {
        finish();
        return;
      }
    } catch {
      finish();
      return;
    }
    timer = setTimeout(() => void poll(), intervalMs);
  };
  void poll();

  return () => {
    cancelled = true;
    if (timer) clearTimeout(timer);
  };
}
