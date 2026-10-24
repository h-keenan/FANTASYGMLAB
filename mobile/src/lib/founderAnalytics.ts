import type { FounderAnalyticsReport } from './api';

/**
 * Founder Analytics helpers. `isFounderSession` mirrors web-next's
 * navDestinations.isFounderSession: the server-issued Supabase Auth
 * `app_metadata.founder_ops` claim. This is a UX gate only (hides the orb row
 * and bounces the screen); GET /v1/founder/analytics enforces the same claim
 * server-side and returns 403 for everyone else, so no data ever reaches a
 * non-founder. Pure (no react-native import) so it is unit-testable.
 */
export function isFounderSession(
  session: { user?: { app_metadata?: Record<string, unknown> | null } | null } | null | undefined,
): boolean {
  return session?.user?.app_metadata?.founder_ops === true;
}

export interface FounderRow {
  key: string;
  label: string;
  value: string;
}

const n = (v: number) => v.toLocaleString('en-US');
const words = (s: string) => s.replace(/_/g, ' ');

export function storageBadge(storage: FounderAnalyticsReport['storage']): { durable: boolean; title: string; detail: string } {
  const durable = storage.kind === 'supabase';
  return {
    durable,
    title: durable ? 'Durable: Supabase' : 'Host-local only',
    detail: `${storage.multi_instance} Retention ${storage.retention_days} days. Writes ${storage.writes_enabled ? 'enabled' : 'disabled'}.`,
  };
}

export function summaryTiles(r: FounderAnalyticsReport): FounderRow[] {
  return [
    { key: 'events', label: 'Events', value: n(r.event_count) },
    { key: 'sessions', label: 'Sessions', value: n(r.sessions) },
    { key: 'anon', label: 'Anonymous users', value: n(r.anonymous_users) },
    { key: 'accounts', label: 'Accounts', value: n(r.hashed_accounts) },
  ];
}

export function moduleRows(r: FounderAnalyticsReport): FounderRow[] {
  return r.product_modules.map((m) => ({
    key: m.module,
    label: words(m.module),
    value: `${n(m.views)} views · ${n(m.users)} users · ${n(m.sessions)} sessions`,
  }));
}

export function namedCountRows(items: { event: string; label: string; count: number }[]): FounderRow[] {
  return items.map((i) => ({ key: i.event, label: i.label, value: n(i.count) }));
}

export function featureUseRows(r: FounderAnalyticsReport): FounderRow[] {
  return (r.feature_use ?? []).map((f) => ({
    key: `${f.feature}:${f.action}`,
    label: `${words(f.feature)} · ${words(f.action)}`,
    value: `${n(f.total)} · web ${f.web} / ios ${f.ios} / android ${f.android} · free ${f.free} / pro ${f.pro}`,
  }));
}

export function funnelSummary(r: FounderAnalyticsReport): string | null {
  const f = r.onboarding_funnel;
  if (!f || f.steps.length === 0) return null;
  const parts = [`${n(f.started_users)} users started`];
  if (f.completion_rate_pct !== null) parts.push(`completion ${f.completion_rate_pct}%`);
  if (f.skip_rate_pct !== null) parts.push(`skip rate ${f.skip_rate_pct}%`);
  return parts.join(' · ');
}

export function funnelRows(r: FounderAnalyticsReport): FounderRow[] {
  return (r.onboarding_funnel?.steps ?? []).map((s) => ({
    key: s.step,
    label: words(s.step),
    value:
      `${n(s.users)} users` +
      (s.drop_off_pct !== null ? ` · drop-off ${s.drop_off_pct}%` : '') +
      (s.skipped_users > 0 ? ` · skipped ${s.skipped_users}` : ''),
  }));
}

export function errorRows(r: FounderAnalyticsReport): FounderRow[] {
  return Object.entries(r.errors).map(([k, c]) => ({ key: k, label: k, value: n(c) }));
}

export function performanceRows(r: FounderAnalyticsReport): FounderRow[] {
  return Object.entries(r.performance).map(([k, s]) => ({
    key: k,
    label: words(k),
    value: `p50 ${s.p50 ?? '—'} · p90 ${s.p90 ?? '—'} · p95 ${s.p95 ?? '—'} (n=${s.n})`,
  }));
}

export function platformLine(r: FounderAnalyticsReport): string | null {
  if (!r.platforms) return null;
  const parts = Object.entries(r.platforms).map(([p, c]) => `${p} ${n(c)}`);
  return parts.length ? `Events by platform: ${parts.join(' · ')}` : null;
}
