import type { RoundupPredictability, RoundupSwap } from "@/lib/api";

/** Pure copy/tone helpers for the Weekly Roundup tab. Twin of
 * mobile/src/lib/roundupPresentation.ts (keep in sync). */

export const PREDICTABILITY_LABEL: Record<RoundupPredictability, string> = {
  foreseeable: "Foreseeable",
  coin_flip: "Coin flip",
  unforeseeable: "Unforeseeable",
};

/** One fixed semantic color per tag, never reused for anything else here:
 * foreseeable = danger (a lesson), coin flip = warning, unforeseeable = information. */
export function predictabilityColorVar(tag: RoundupPredictability): string {
  if (tag === "foreseeable") return "var(--color-danger)";
  if (tag === "coin_flip") return "var(--color-warning)";
  return "var(--color-information)";
}

export function formatPoints(value: number | null | undefined): string {
  return Number.isFinite(value) ? (value as number).toFixed(1) : "0.0";
}

export function swapLine(swap: RoundupSwap): string {
  return `${swap.started.name} (${formatPoints(swap.started.points)}) over ${swap.benched.name} (${formatPoints(swap.benched.points)})`;
}

const REASON_MESSAGES: Record<string, { title: string; subtitle: string }> = {
  no_completed_week: {
    title: "No roundup yet",
    subtitle: "Your roundup appears once a week of games is final. Check back after the week's matchups finish scoring.",
  },
  no_matchup_data: {
    title: "No lineup on record for this week",
    subtitle: "Sleeper has no lineup for your team in this week, so there is nothing to compare.",
  },
  unsupported_platform: {
    title: "Roundup is not available for this league type yet",
    subtitle: "The weekly roundup needs Sleeper lineup history. ESPN, Fleaflicker and MFL leagues are not supported yet.",
  },
  no_sleeper_username_linked: {
    title: "Link your Sleeper account",
    subtitle: "Link your Sleeper username in Account so we can find your team in this league.",
  },
  not_a_member_of_league: {
    title: "We could not find your team",
    subtitle: "Your linked Sleeper account does not own a team in this league.",
  },
};

export function roundupReasonMessage(reason: string): { title: string; subtitle: string } {
  return (
    REASON_MESSAGES[reason] ?? {
      title: "Roundup is not ready",
      subtitle: "We could not build your roundup right now. Try again in a moment.",
    }
  );
}

/** 1..max, newest first is not needed: the week picker reads left to right. */
export function roundupWeeks(maxWeek: number): number[] {
  return Array.from({ length: Math.max(0, Math.floor(maxWeek)) }, (_, i) => i + 1);
}

/** Bar width (0..100) for a week's bench regret against the season's worst week. */
export function regretBarPercent(left: number, worst: number): number {
  if (!(worst > 0) || !(left > 0)) return 0;
  return Math.max(4, Math.min(100, Math.round((left / worst) * 100)));
}
