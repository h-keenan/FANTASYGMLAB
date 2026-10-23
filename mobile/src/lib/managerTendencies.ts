/** Manager Tendencies (GET /v1/leagues/{id}/managers/tendencies and
 * .../{roster_id}/tendencies, Premium). Mirrors web-next/src/lib/managerTendencies.ts. */

export interface ManagerTendencySignal {
  status: 'ok' | 'insufficient_data';
  label: string | null;
  summary: string;
  sample_size: number;
  min_sample: number;
  evidence: string[];
}

export interface ManagerTendencySummaryRow {
  roster_id: number;
  team_name: string | null;
  owner_handle: string | null;
  headline: string | null;
}

export interface ManagerTendenciesSummaryResponse {
  ok: boolean;
  is_premium: boolean;
  upsell: { title: string; body: string } | null;
  managers: ManagerTendencySummaryRow[];
}

export interface ManagerRecentTradeAsset {
  kind: 'player' | 'pick';
  player_id?: string;
  name?: string;
  position?: string;
  team?: string;
  season?: string;
  round?: number | null;
  label?: string;
  original_team?: string;
}

export interface ManagerRecentTrade {
  transaction_id: string;
  season: string;
  week: number;
  date: string;
  partners: string[];
  received: ManagerRecentTradeAsset[];
  sent: ManagerRecentTradeAsset[];
  /** Our retrospective letter for the manager's side; null when not computable. */
  grade: { letter: string; tone: string; confidence: string; timing_label: string; ratio: number | null } | null;
}

/** Grade tone slug (server) -> shared semantic color slug. */
export function gradeToneSlug(tone: string | null | undefined): 'success' | 'accent' | 'muted' | 'danger' {
  if (tone === 'success') return 'success';
  if (tone === 'positive') return 'accent';
  if (tone === 'risk') return 'danger';
  return 'muted';
}

/** "2026-10-04" -> "Oct 4, 2026 · Wk 5" (week-only fallback; '' if neither). */
export function tradeDateLabel(date: string | null | undefined, week?: number | null): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(date ?? '');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const base = match ? `${months[Number(match[2]) - 1] ?? ''} ${Number(match[3])}, ${match[1]}` : '';
  if (base && week) return `${base} · Wk ${week}`;
  if (base) return base;
  return week ? `Week ${week}` : '';
}

export interface ManagerTendenciesDetailResponse {
  ok: boolean;
  is_premium: boolean;
  upsell: { title: string; body: string } | null;
  manager: {
    team_name: string | null;
    headline: string | null;
    sample?: { trades: number; wire_moves: number; seasons: number } | null;
    signals: Record<string, ManagerTendencySignal>;
  } | null;
  /** Pro payload only; newest first, max 5. */
  recent_trades?: ManagerRecentTrade[];
}

/** Signal order + short titles (mirrors modules.manager_tendencies.SIGNAL_ORDER). */
export const TENDENCY_SIGNALS: Array<[string, string]> = [
  ['posture', 'Posture'],
  ['position_preference', 'Positions'],
  ['age_preference', 'Age'],
  ['pick_behavior', 'Picks'],
  ['package_shape', 'Package shape'],
  ['trade_frequency', 'Trade rate'],
  ['waiver_activity', 'Waivers'],
  ['trade_partners', 'Partners'],
];

/** Short chips from a server headline, dropping "not enough trades"/"no
 * strong tendencies" lead-ins so only real reads remain. */
export function headlineChips(headline: string | null | undefined, max = 3): string[] {
  return (headline ?? '')
    .split(/\.\s+|\.$/)
    .map((part) => part.trim())
    .filter((part) => part && !/^(not enough|no strong|no owner)/i.test(part))
    .slice(0, max);
}

export function findManagerRow(
  data: ManagerTendenciesSummaryResponse | undefined,
  teamName: string,
  rosterId?: string | number,
): ManagerTendencySummaryRow | undefined {
  if (!data) return undefined;
  if (rosterId !== undefined && rosterId !== '') {
    const byId = data.managers.find((m) => String(m.roster_id) === String(rosterId));
    if (byId) return byId;
  }
  const name = teamName.trim().toLowerCase();
  if (!name) return undefined;
  return data.managers.find((m) => (m.team_name ?? '').trim().toLowerCase() === name);
}

export type TendencyTone = 'success' | 'warning' | 'accent' | 'premium';

const LABEL_TONES: Record<string, TendencyTone> = {
  contending: 'success',
  very_active_on_waivers: 'success',
  trades_more_than_most: 'success',
  aggressive_faab: 'success',
  rebuilding: 'warning',
  quiet_on_waivers: 'warning',
  trades_less_than_most: 'warning',
  conservative_faab: 'warning',
  buys_picks: 'accent',
  acquires_younger: 'accent',
  consolidates: 'accent',
  has_frequent_partners: 'accent',
  sells_picks: 'premium',
  acquires_older: 'premium',
  splits: 'premium',
};

/** Semantic tone for a signal label (server label slugs, never made up). */
export function tendencyTone(label: string | null | undefined): TendencyTone {
  return (label && LABEL_TONES[label]) || 'accent';
}

/** 'very_active_on_waivers' -> 'Very active on waivers'; null for no label. */
export function tendencyBadgeText(label: string | null | undefined): string | null {
  if (!label) return null;
  const text = label.replace(/_/g, ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : null;
}

/** Evidence meter fill (0-1): sample size against the signal's minimum, capped. */
export function sampleFill(sampleSize: number, minSample: number): number {
  const target = Math.max(1, minSample) * 2;
  return Math.max(0, Math.min(1, sampleSize / target));
}
