/**
 * Pure presentation for "Your track record" and the per-trade outcome line (Decision Memory depth).
 * Import-free, byte-identical twin of mobile/src/lib/trackRecordView.ts. All numbers come from
 * modules/decision_log.py; this only words them, and refuses to word anything the sample does not support
 * (too few graded decisions reads as "too early", never as a rate).
 */

export type TrackReliability = "too_early" | "early" | "solid";
export type TrackLevel = "low" | "medium" | "high";

export interface TrackHit {
  n: number;
  right: number;
  wrong: number;
  hit_rate: number | null;
  mean_edge_pts: number | null;
  reliability: TrackReliability;
}

export interface TrackCalibrationBucket extends TrackHit {
  supported: boolean;
}

export interface TrackBasicView {
  trades_confirmed: number;
  trades_graded: number;
  worked_out: number;
  didnt_pan_out: number;
  net_points_total: number;
  reliability: TrackReliability;
}

export interface TrackAdvancedView {
  advice: TrackHit;
  own_calls: TrackHit;
  compare: { verdict: "too_early" | "within_noise" | "advice_ahead" | "own_ahead"; diff_pts?: number };
  calibration: Record<TrackLevel, TrackCalibrationBucket>;
}

/** A graded trade's real production line, as stored by the result sweep. */
export interface TradeProductionView {
  status: string;
  production?: { net_points_ppr: number; weeks_counted: number } | null;
}

/** Fewest graded decisions before any rate is shown (mirrors decision_log.MIN_TRACK_SAMPLE). */
export const MIN_TRACK_SAMPLE = 5;

export function signedPts(points: number): string {
  const rounded = Math.round(points);
  return `${rounded > 0 ? "+" : ""}${rounded} pts`;
}

/** "This trade: +34 pts for you so far", or null until a real production number exists. */
export function tradePointsLine(result: TradeProductionView | null | undefined): string | null {
  if (!result || result.status !== "ready" || !result.production) return null;
  const { net_points_ppr: net, weeks_counted: weeks } = result.production;
  if (typeof net !== "number" || Number.isNaN(net)) return null;
  const span = weeks > 0 ? ` over ${weeks} ${weeks === 1 ? "wk" : "wks"}` : "";
  if (Math.round(net) === 0) return `This trade: even so far${span}`;
  return `This trade: ${signedPts(net)} for you so far${span}`;
}

export function reliabilityLabel(reliability: TrackReliability): string {
  if (reliability === "too_early") return "Too early to read";
  if (reliability === "early") return "Early read";
  return "Solid sample";
}

export function plural(n: number, one: string, many: string = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The one-line collapsed summary for the basic (free) record. */
export function basicSummary(basic: TrackBasicView): string[] {
  if (basic.trades_graded === 0) {
    return basic.trades_confirmed > 0 ? [`${plural(basic.trades_confirmed, "confirmed trade")}`, "results still coming in"] : ["No graded trades yet"];
  }
  const parts = [`${basic.worked_out} worked out`, `${basic.didnt_pan_out} didn't`];
  parts.push(`${signedPts(basic.net_points_total)} net`);
  if (basic.reliability === "too_early") parts.push("too early to read");
  return parts;
}

/** How our advice did vs the user's own calls. Claims a gap only when the server found one past noise. */
export function compareLine(adv: TrackAdvancedView): string {
  const a = adv.advice;
  const o = adv.own_calls;
  if (adv.compare.verdict === "too_early") {
    return `Need at least ${MIN_TRACK_SAMPLE} graded of each to compare (advice ${a.n}, your own ${o.n}).`;
  }
  const diff = Math.abs(Math.round(adv.compare.diff_pts ?? 0));
  if (adv.compare.verdict === "within_noise") {
    return `Advice and your own calls are within noise of each other (${diff} pts apart). At this sample that gap is as likely luck as skill.`;
  }
  const who = adv.compare.verdict === "advice_ahead" ? "Our advice" : "Your own calls";
  return `${who} is ahead by about ${diff} pts per decision, beyond what luck usually explains at this sample (${a.n} advice, ${o.n} own).`;
}

/**
 * Calibrate the wording of a confidence label from the user's graded history. Only speaks when that
 * confidence level has enough graded decisions (server `supported`); otherwise returns null and the original
 * wording stays untouched. A level that has not held up is softened; one that has is confirmed.
 */
export function calibrationNote(label: string | null | undefined, adv: TrackAdvancedView | null | undefined): string | null {
  if (!label || !adv) return null;
  const level = label.trim().toLowerCase().split(/\s+/)[0] as TrackLevel;
  const bucket = adv.calibration?.[level];
  if (!bucket || !bucket.supported || bucket.hit_rate === null) return null;
  const decided = bucket.right + bucket.wrong;
  const held = `${bucket.right} of ${decided}`;
  const name = level.charAt(0).toUpperCase() + level.slice(1);
  if (bucket.hit_rate >= 0.6) return `${name}-confidence advice has held up ${held} times for you.`;
  if (bucket.hit_rate <= 0.4) return `${name}-confidence advice has held up only ${held} times for you, so weigh it lighter.`;
  return `${name}-confidence advice is about a coin flip for you so far (${held}).`;
}
