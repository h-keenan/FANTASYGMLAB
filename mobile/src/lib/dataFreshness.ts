/**
 * THE "as of" wording for data that can be stale (data-truth audit 2026-11-19, docs/audits/2026-11-data-truth.md, finding 4).
 * One pure module, byte-identical on web and mobile (twin: mobile/src/lib/dataFreshness.ts); the fetch hook and the
 * FreshnessLabel component are the only platform pieces. The source is the public report GET /v1/public/data-freshness
 * (modules/data_freshness.py), whose rows carry `as_of` in epoch seconds.
 *
 * Honesty rules: no timestamp means no label (never a guess); the values row is trusted only when the server says its
 * timestamp is a real provider fetch (`as_of_source: "fetch_timestamp"`), because a file mtime is the git checkout time;
 * over-threshold data says "may be behind" in plain muted text (never an error colour).
 */
export type FreshnessDataset = "values" | "injuries" | "prospects" | "schedule" | "stats" | "adp" | "league";

export interface FreshnessRow {
  name?: string;
  as_of?: number | null;
  as_of_source?: string | null;
}

export interface FreshnessReport {
  datasets?: FreshnessRow[];
}

/** Report row name, label, wording style and the age (hours) past which the label adds "may be behind". */
const DATASETS: Record<FreshnessDataset, { row: string; label: string; style: "ago" | "clock"; staleHours: number }> = {
  values: { row: "values_fantasycalc", label: "Values", style: "ago", staleHours: 30 },
  injuries: { row: "players_db_and_injury_status", label: "Injuries", style: "clock", staleHours: 12 },
  prospects: { row: "college_prospects", label: "Prospects", style: "clock", staleHours: 216 },
  schedule: { row: "schedule_nflverse", label: "Schedule", style: "ago", staleHours: 192 },
  stats: { row: "weekly_stats", label: "Stats", style: "ago", staleHours: 30 },
  adp: { row: "adp_rookie_dynasty", label: "ADP", style: "ago", staleHours: 72 },
  // Not in the public report: the API stamps `sleeper_data_as_of` on a league response served from last-known provider data
  // after a failed refresh (429 / timeout / outage). Shown only then, so it always reads "may be behind".
  league: { row: "", label: "League data", style: "ago", staleHours: 0 },
};

/** Epoch seconds the dataset was last refreshed, or null when the report cannot say so honestly. */
export function freshnessAsOf(report: FreshnessReport | null | undefined, dataset: FreshnessDataset): number | null {
  const spec = DATASETS[dataset];
  const row = report?.datasets?.find((r) => r.name === spec.row);
  const asOf = row?.as_of;
  if (typeof asOf !== "number" || !Number.isFinite(asOf) || asOf <= 0) return null;
  if (dataset === "values" && row?.as_of_source !== "fetch_timestamp") return null;
  return asOf;
}

function clockTime(date: Date): string {
  const hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours % 12 === 0 ? 12 : hours % 12}:${minutes}${hours < 12 ? "am" : "pm"}`;
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Values as of 2h ago", "Injuries updated 9:40am", "Injuries updated yesterday 9:40am", "Prospects updated Nov 12". */
export function freshnessText(dataset: FreshnessDataset, asOfSeconds: number, nowMs: number): string {
  const spec = DATASETS[dataset];
  const when = new Date(asOfSeconds * 1000);
  const ageMs = Math.max(0, nowMs - asOfSeconds * 1000);
  const ageHours = ageMs / 3_600_000;
  let text: string;
  if (spec.style === "ago") {
    const minutes = Math.floor(ageMs / 60_000);
    const ago = minutes < 1 ? "just now" : minutes < 60 ? `${minutes}m ago` : ageHours < 48 ? `${Math.floor(ageHours)}h ago` : `${Math.floor(ageHours / 24)}d ago`;
    text = `${spec.label} as of ${ago}`;
  } else {
    const days = Math.round((startOfDay(new Date(nowMs)) - startOfDay(when)) / 86_400_000);
    const at = days <= 0 ? clockTime(when) : days === 1 ? `yesterday ${clockTime(when)}` : `${MONTHS[when.getMonth()]} ${when.getDate()}`;
    text = `${spec.label} updated ${at}`;
  }
  return ageHours > spec.staleHours ? `${text} (may be behind)` : text;
}

/** The label for a dataset, or null when there is nothing honest to say. */
export function freshnessLabel(report: FreshnessReport | null | undefined, dataset: FreshnessDataset, nowMs: number): string | null {
  const asOf = freshnessAsOf(report, dataset);
  return asOf == null ? null : freshnessText(dataset, asOf, nowMs);
}

/**
 * "League data as of 12m ago (may be behind)" for a league response the API served from last-known provider data after a
 * failed refresh (its `sleeper_data_as_of`, an ISO time). Null for live data (no stamp) or an unreadable stamp, never a guess.
 */
export function leagueStaleLabel(asOfIso: string | null | undefined, nowMs: number): string | null {
  if (!asOfIso) return null;
  const ms = Date.parse(asOfIso);
  if (!Number.isFinite(ms) || ms <= 0) return null;
  return freshnessText("league", ms / 1000, nowMs);
}
