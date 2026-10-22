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

export interface ManagerTendenciesDetailResponse {
  ok: boolean;
  is_premium: boolean;
  upsell: { title: string; body: string } | null;
  manager: {
    team_name: string | null;
    headline: string | null;
    signals: Record<string, ManagerTendencySignal>;
  } | null;
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
