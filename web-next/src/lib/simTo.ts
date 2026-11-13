// Shared (web + mobile twin): plain-words presentation of a "Sim to..." run. Pure and import-free of runtime code.

import type { SimToStop, SimToSummary, SimToWeek } from "./simGame";

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
      return stop.code === "empty_slot" ? "Fill the slot" : "Fix lineup";
    case "roster":
      return "Make cuts";
    case "inbox":
      return "Answer offers";
    case "premium":
      return "Go Pro";
    default:
      return null;
  }
}

/** Stops the user may sim past with "Sim anyway" (never the hard ones: a cut owed, the paywall). */
export function simToCanForce(stop: Pick<SimToStop, "code">): boolean {
  return stop.code === "starter_out" || stop.code === "starter_bye" || stop.code === "empty_slot" || stop.code === "trade_offers";
}

/** The tab a fix opens. */
export function simToFixTab(stop: Pick<SimToStop, "fix">): "team" | "trades" | null {
  return stop.fix === "lineup" || stop.fix === "roster" ? "team" : stop.fix === "inbox" ? "trades" : null;
}

/** "Simulating to the trade deadline..." while the single request is in flight. */
export function simToProgressLabel(label: string): string {
  return `Simulating: ${label.charAt(0).toLowerCase()}${label.slice(1)}...`;
}
