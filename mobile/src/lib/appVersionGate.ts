/**
 * Minimum-supported-version gate. The server (`GET /v1/app-config`,
 * modules/app_version_policy.py) says the lowest app version allowed per
 * platform; below it the app shows a blocking "Update required" screen.
 * FAIL OPEN: any network/parse problem, or no floor configured, lets the app run.
 */

export interface AppConfigResponse {
  min_app_version?: { ios?: string; android?: string };
  store_urls?: { ios?: string; android?: string };
}

export interface GateDecision {
  updateRequired: boolean;
  storeUrl: string;
}

export function parseVersion(raw: string): number[] | null {
  const text = String(raw ?? '').trim().replace(/^v/i, '');
  if (!/^\d+(\.\d+){0,3}$/.test(text)) return null;
  return text.split('.').map(Number);
}

/** <0 if a<b, 0 if equal, >0 if a>b. Missing segments count as 0. Null when either is unparseable. */
export function compareVersions(a: string, b: string): number | null {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  if (!pa || !pb) return null;
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d !== 0) return d;
  }
  return 0;
}

export function decideGate(
  config: AppConfigResponse | null | undefined,
  platform: 'ios' | 'android' | string,
  currentVersion: string,
): GateDecision {
  const key = platform === 'ios' ? 'ios' : platform === 'android' ? 'android' : null;
  if (!key || !config) return { updateRequired: false, storeUrl: '' };
  const min = config.min_app_version?.[key] ?? '';
  const storeUrl = config.store_urls?.[key] ?? '';
  const cmp = min ? compareVersions(currentVersion, min) : null;
  return { updateRequired: cmp !== null && cmp < 0, storeUrl };
}

export async function fetchGate(opts: {
  apiBaseUrl: string;
  platform: string;
  currentVersion: string;
  fetchFn?: (url: string, init: { signal: AbortSignal }) => Promise<{ ok: boolean; json: () => Promise<unknown> }>;
  timeoutMs?: number;
}): Promise<GateDecision> {
  const open: GateDecision = { updateRequired: false, storeUrl: '' };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 5000);
  try {
    const doFetch = opts.fetchFn ?? ((url, init) => fetch(url, init));
    const res = await doFetch(`${opts.apiBaseUrl.replace(/\/+$/, '')}/v1/app-config`, { signal: controller.signal });
    if (!res.ok) return open;
    return decideGate((await res.json()) as AppConfigResponse, opts.platform, opts.currentVersion);
  } catch {
    return open;
  } finally {
    clearTimeout(timer);
  }
}
