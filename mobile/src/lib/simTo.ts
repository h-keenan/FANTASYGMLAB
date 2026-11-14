// Shared (web + mobile twin): plain-words presentation of a "Sim to..." run. Pure and import-free of runtime code.

import type { SimToOption, SimToStop, SimToStops, SimToSummary, SimToWeek } from "./simGame";

/** "Simmed 4 weeks (Weeks 3-6)" / "Simmed Week 3" / "Simulated the playoffs". */
export function simToHeadline(weeksPlayed: number, summary: Pick<SimToSummary, "weeks"> | null | undefined): string {
  const weeks = summary?.weeks ?? [];
  if (weeksPlayed <= 0 || weeks.length === 0) return "Nothing simulated";
  const first = weeks[0].week;
  const last = weeks[weeks.length - 1].week;
  if (weeks.every((w) => w.kind === "playoff")) return weeksPlayed === 1 ? "Played a playoff round" : `Played ${weeksPlayed} playoff rounds`;
  return weeksPlayed === 1 ? `Simmed Week ${first}` : `Simmed ${weeksPlayed} weeks (Weeks ${first}-${last})`;
}

/** "W 112.4-98.7 vs Rats" for one simmed week, "Bye" or "-" when no game. */
export function simToWeekLine(w: SimToWeek): string {
  if (w.result === "bye") return "Bye week";
  if (!w.result) return "No game";
  const r = w.result.toUpperCase();
  const pts = w.your_pts != null && w.opp_pts != null ? ` ${w.your_pts.toFixed(1)}-${w.opp_pts.toFixed(1)}` : "";
  return `${r}${pts}${w.opponent ? ` vs ${w.opponent}` : ""}`;
}

export function simToRecordLine(s: Pick<SimToSummary, "record" | "rank">): string {
  const rec = s.record.before && s.record.after && s.record.before !== s.record.after ? `${s.record.before} to ${s.record.after}` : (s.record.after ?? "");
  const rank = s.rank.after != null ? (s.rank.before != null && s.rank.before !== s.rank.after ? `#${s.rank.before} to #${s.rank.after}` : `#${s.rank.after}`) : "";
  return [rec, rank].filter(Boolean).join(" · ");
}

/** The button label that takes the user to where a stop is fixed. */
export function simToFixLabel(stop: Pick<SimToStop, "fix" | "code">): string | null {
  switch (stop.fix) {
    case "lineup":
      return stop.code === "empty_slot" ? "Fill the slot" : stop.code === "starter_injured" ? "Review lineup" : "Fix lineup";
    case "roster":
      return stop.code === "waiver_issue" ? "Fix claims" : "Make cuts";
    case "inbox":
      return stop.code === "trade_deadline" ? "Open trades" : "Answer offers";
    case "premium":
      return "Go Pro";
    default:
      return null;
  }
}

/** Stops the user may sim past with "Sim anyway" (never the hard ones: a cut owed, the paywall). */
export function simToCanForce(stop: Pick<SimToStop, "code">): boolean {
  return (
    stop.code === "starter_out" ||
    stop.code === "starter_bye" ||
    stop.code === "empty_slot" ||
    stop.code === "trade_offers" ||
    stop.code === "starter_injured" ||
    stop.code === "trade_deadline" ||
    stop.code === "waiver_issue"
  );
}

/** The tab a fix opens. */
export function simToFixTab(stop: Pick<SimToStop, "fix">): "team" | "trades" | null {
  return stop.fix === "lineup" || stop.fix === "roster" ? "team" : stop.fix === "inbox" ? "trades" : null;
}

/** "Simulating to the trade deadline..." while the single request is in flight. */
export function simToProgressLabel(label: string): string {
  return `Simulating: ${label.charAt(0).toLowerCase()}${label.slice(1)}...`;
}

// ---------------------------------------------------------------------------
// Per-run toggles (persisted on the device) and the end-of-run readout

export interface SimToPrefs {
  /** Auto-set my lineup before every simulated week (Madden / 2K franchise auto-play). On by default. */
  autoSet: boolean;
  stops: SimToStops;
}

export const SIM_TO_PREFS_KEY = "fgl:sim-to-prefs";

export const SIM_TO_DEFAULT_PREFS: SimToPrefs = {
  autoSet: true,
  stops: { offers: true, injuries: true, starters: true, deadline: true, roster: true },
};

/** The rows of the toggle list, in display order. */
export const SIM_TO_STOP_ROWS: readonly { key: keyof SimToStops; label: string; hint: string }[] = [
  { key: "offers", label: "Incoming trade offers", hint: "Stop when an AI team sends you an offer" },
  { key: "injuries", label: "Injuries to my starters", hint: "Stop when one of my starters gets hurt" },
  { key: "starters", label: "A starter is out or on a bye", hint: "Only if nothing on the bench can fix it" },
  { key: "deadline", label: "Trade deadline", hint: "Stop in the last week trades are allowed" },
  { key: "roster", label: "Waiver or roster issues", hint: "A claim that cannot go through" },
];

/** Read stored prefs; anything missing or malformed falls back to the default for that field. */
export function simToParsePrefs(raw: string | null | undefined): SimToPrefs {
  const d = SIM_TO_DEFAULT_PREFS;
  if (!raw) return { autoSet: d.autoSet, stops: { ...d.stops } };
  try {
    const v = JSON.parse(raw) as { autoSet?: unknown; stops?: Record<string, unknown> } | null;
    const stops = { ...d.stops };
    for (const k of Object.keys(stops) as (keyof SimToStops)[]) {
      const x = v?.stops?.[k];
      if (typeof x === "boolean") stops[k] = x;
    }
    return { autoSet: typeof v?.autoSet === "boolean" ? v.autoSet : d.autoSet, stops };
  } catch {
    return { autoSet: d.autoSet, stops: { ...d.stops } };
  }
}

export function simToSerializePrefs(prefs: SimToPrefs): string {
  return JSON.stringify(prefs);
}

/** How many of the stops are on, for the collapsed row ("5 of 5 stops on"). */
export function simToStopCount(stops: SimToStops): number {
  return SIM_TO_STOP_ROWS.filter((r) => stops[r.key]).length;
}

/** The compact "what happened" lines under the headline: lineup changes, offers waiting, roster over the limit. */
export function simToReadout(s: SimToSummary): string[] {
  const out: string[] = [];
  const changes = s.lineup_changes ?? [];
  if (s.auto_set) {
    const weeks = new Set(changes.map((c) => c.week)).size;
    out.push(changes.length === 0 ? "Lineup auto-set: no changes needed." : `Lineup auto-set: ${changes.length} change${changes.length === 1 ? "" : "s"} over ${weeks} week${weeks === 1 ? "" : "s"}.`);
  }
  if ((s.offers_pending ?? 0) > 0) out.push(`${s.offers_pending} trade offer${s.offers_pending === 1 ? "" : "s"} waiting${(s.offers_new ?? 0) > 0 ? ` (${s.offers_new} new)` : ""}.`);
  if ((s.roster?.over ?? 0) > 0) out.push(`Over the limit by ${s.roster?.over}: cut or trade to add players.`);
  if (s.injuries.length > 0) out.push(`${s.injuries.length} injur${s.injuries.length === 1 ? "y" : "ies"} to your players.`);
  return out;
}

/** "Keep simming" after a stop partway through: a weeks target only has the weeks that are left; the other targets are unchanged. */
export function simToRemaining(option: SimToOption, played: number): SimToOption {
  return option.id === "weeks" && option.weeks ? { ...option, weeks: Math.max(1, option.weeks - Math.max(0, played)) } : option;
}
