/**
 * Mobile product-analytics core. Pure (no React Native / Expo imports) so it
 * is unit-testable with `node --test`; analytics.ts wires the real
 * AsyncStorage / fetch / AppState / Supabase dependencies.
 *
 * Same wire format as web-next/src/lib/analytics.ts and the same backend
 * ingest (`POST /v1/analytics/event`, modules.launch_analytics): events are
 * `{event, props, anon_id}`; generic feature interactions are the
 * `feature_use` event with `feature` / `action` / optional `tier` props, and a
 * `platform` prop ("ios" | "android") so the founder dashboard can split and
 * combine platforms.
 *
 * Guarantees:
 *  - Disabled (kill switch) => nothing is queued, stored, or sent.
 *  - Never throws and never awaits on the UI path: track() is synchronous
 *    and only touches an in-memory queue; persistence and network are
 *    fire-and-forget with every failure swallowed.
 *  - Bounded: the queue is capped (oldest dropped) and persisted so a short
 *    offline period or app kill does not lose events.
 *  - Privacy: only allowlisted prop keys, primitive values, short strings;
 *    never emails, tokens, names, or league/player ids. Routes are screen
 *    names, never params.
 */

export interface AnalyticsEvent {
  event: string;
  props: Record<string, string | number | boolean>;
  anon_id: string;
  /** Epoch ms the event happened (not sent; used for ordering/expiry). */
  ts: number;
}

export interface AnalyticsStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

export interface AnalyticsDeps {
  /** Kill switch, evaluated on every call so it can flip at runtime. */
  enabled: () => boolean;
  /** POST one event. Reject/throw on failure (the core swallows it). */
  send: (event: AnalyticsEvent) => Promise<void>;
  storage: AnalyticsStorage;
  platform: 'ios' | 'android' | 'web' | string;
  now?: () => number;
  randomId?: () => string;
  maxQueue?: number;
  /** Max events sent per flush(). */
  batchSize?: number;
  /** Drop queued events older than this (default 3 days). */
  maxAgeMs?: number;
}

export const ANON_ID_KEY = 'dynastygm_analytics_anon_id';
export const QUEUE_KEY = 'dynastygm_analytics_queue_v1';

/** Mirrors modules.launch_analytics.ALLOWED_PROP_KEYS (client-safe subset). */
const ALLOWED_PROP_KEYS = new Set([
  'route',
  'source_surface',
  'feature',
  'action',
  'tier',
  'platform',
  'result',
  'reason',
  'item_kind',
  'destination',
  'interval',
  'trigger',
  'error_class',
  // Onboarding funnel (feature_use feature=onboarding) -- fixed ids/indices.
  // These were missing, so every mobile onboarding event reached the backend
  // with its step / step_index / experience stripped.
  'step',
  'step_index',
  'experience',
  // Push pre-prompt outcome (granted | denied | undetermined).
  'os_result',
  'league_id', // hashed server-side into league_key, never stored raw
]);

/** Parse the EXPO_PUBLIC_ANALYTICS_ENABLED flag. Absent/unknown => OFF. */
export function parseAnalyticsFlag(value: string | undefined | null): boolean {
  return ['1', 'true', 'yes', 'on'].includes(String(value ?? '').trim().toLowerCase());
}

export function sanitizeProps(
  props: Record<string, unknown> | undefined,
): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(props ?? {})) {
    if (!ALLOWED_PROP_KEYS.has(key)) continue;
    if (typeof value === 'string') out[key] = value.trim().slice(0, 80);
    else if (typeof value === 'number' && Number.isFinite(value)) out[key] = value;
    else if (typeof value === 'boolean') out[key] = value;
  }
  return out;
}

function defaultRandomId(): string {
  let out = '';
  for (let i = 0; i < 16; i += 1) out += Math.floor(Math.random() * 16).toString(16);
  return out;
}

export function createAnalytics(deps: AnalyticsDeps) {
  const now = deps.now ?? (() => Date.now());
  const randomId = deps.randomId ?? defaultRandomId;
  const maxQueue = deps.maxQueue ?? 200;
  const batchSize = deps.batchSize ?? 25;
  const maxAgeMs = deps.maxAgeMs ?? 3 * 24 * 60 * 60 * 1000;

  let queue: AnalyticsEvent[] = [];
  let anonId: string | null = null;
  let hydrated: Promise<void> | null = null;
  let flushing: Promise<void> | null = null;

  const isEnabled = (): boolean => {
    try {
      return Boolean(deps.enabled());
    } catch {
      return false;
    }
  };

  async function persist(): Promise<void> {
    try {
      await deps.storage.setItem(QUEUE_KEY, JSON.stringify(queue));
    } catch {
      // best effort
    }
  }

  function hydrate(): Promise<void> {
    if (!hydrated) {
      hydrated = (async () => {
        try {
          const stored = await deps.storage.getItem(ANON_ID_KEY);
          if (stored) anonId = stored;
        } catch {
          // fall through
        }
        if (!anonId) {
          anonId = `anon_${randomId()}`;
          try {
            await deps.storage.setItem(ANON_ID_KEY, anonId);
          } catch {
            // in-memory id for this launch
          }
        }
        try {
          const raw = await deps.storage.getItem(QUEUE_KEY);
          const parsed: unknown = raw ? JSON.parse(raw) : [];
          if (Array.isArray(parsed)) {
            const cutoff = now() - maxAgeMs;
            const restored = parsed.filter(
              (e): e is AnalyticsEvent =>
                !!e && typeof e === 'object' && typeof (e as AnalyticsEvent).event === 'string' && (e as AnalyticsEvent).ts > cutoff,
            );
            // Persisted events go first (they are older).
            queue = [...restored, ...queue].slice(-maxQueue);
          }
        } catch {
          // corrupt queue => start clean
        }
        // Events tracked before hydration finished carry a placeholder id.
        queue = queue.map((e) => (e.anon_id ? e : { ...e, anon_id: anonId as string }));
      })();
    }
    return hydrated;
  }

  /** Queue one event. Synchronous, never throws, no-op when disabled. */
  function track(event: string, props?: Record<string, unknown>): void {
    try {
      if (!isEnabled()) return;
      const name = (event || '').trim();
      if (!name) return;
      const entry: AnalyticsEvent = {
        event: name,
        props: { ...sanitizeProps(props), platform: deps.platform },
        anon_id: anonId ?? '',
        ts: now(),
      };
      queue.push(entry);
      if (queue.length > maxQueue) queue = queue.slice(queue.length - maxQueue);
      void hydrate().then(persist);
    } catch {
      // never surfaces
    }
  }

  /** feature_use, the cross-platform generic interaction event. */
  function trackUse(
    feature: string,
    action: string = 'used',
    options?: { leagueId?: string; tier?: 'free' | 'pro'; props?: Record<string, unknown> },
  ): void {
    track('feature_use', {
      ...(options?.props ?? {}),
      feature,
      action,
      ...(options?.tier ? { tier: options.tier } : {}),
      ...(options?.leagueId ? { league_id: options.leagueId } : {}),
    });
  }

  /** Screen view; `screen` is a navigator route NAME, never params. */
  function trackScreen(screen: string): void {
    track('page_view', { route: `mobile/${screen}`, source_surface: 'navigation' });
  }

  /**
   * Send up to batchSize queued events in order. Stops at the first failure
   * and keeps the unsent remainder queued for the next flush. Concurrent
   * flush() calls share one in-flight run.
   */
  function flush(): Promise<void> {
    if (!isEnabled()) return Promise.resolve();
    if (flushing) return flushing;
    flushing = (async () => {
      try {
        await hydrate();
        if (!isEnabled() || queue.length === 0) return;
        const cutoff = now() - maxAgeMs;
        queue = queue.filter((e) => e.ts > cutoff);
        const batch = queue.slice(0, batchSize);
        let sent = 0;
        for (const evt of batch) {
          try {
            await deps.send({ ...evt, anon_id: evt.anon_id || (anonId as string) });
            sent += 1;
          } catch {
            break; // offline or server trouble: keep the rest for later
          }
        }
        if (sent > 0) {
          queue = queue.slice(sent);
          await persist();
        }
      } catch {
        // never surfaces
      } finally {
        flushing = null;
      }
    })();
    return flushing;
  }

  return {
    track,
    trackUse,
    trackScreen,
    flush,
    isEnabled,
    /** Test/diagnostic helper. */
    queueSize: () => queue.length,
    ready: hydrate,
  };
}
