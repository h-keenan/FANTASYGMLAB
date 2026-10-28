/**
 * The ONE handler for "the server stopped this request because of a plan
 * limit" results (a `reason` code on an otherwise-ok response). Web and
 * mobile render the model this returns; mobile/src/lib/limitWall.ts is
 * byte-identical and a web test keeps them in sync.
 *
 * It never carries a limit of its own: the number and the reset time come
 * from the API response (`limit`, built in services/mobile_api_service.py
 * from modules.trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT and
 * modules.free_tier_ledger.next_weekly_reset). Without them the copy stays
 * truthful but number-free.
 *
 * Codes handled here: `weekly_limit_reached` (Trade Analyzer, Free) and
 * `premium_required` (Pro-only endpoints that answer ok + reason). Saved
 * league caps (`at_cap`, `free_league_cap`) have their own purpose-built
 * flows (lib/freeLeagueCap.ts, leagueCap.ts) and are intentionally not here.
 */

export type LimitWallCta = "create_account" | "upgrade";

export interface LimitWallInfo {
  limit?: number | null;
  window?: string | null;
  /** ISO timestamp the allowance resets. */
  resets_at?: string | null;
}

export interface LimitWallModel {
  reason: string;
  title: string;
  body: string;
  /** What Pro adds, one line. */
  proLine: string;
  /** Guests may not buy: they are asked to create an account first. */
  cta: LimitWallCta;
  ctaLabel: string;
}

export const LIMIT_WALL_REASONS = ["weekly_limit_reached", "premium_required"] as const;

/** "Monday, 8:00 PM" style local reset time, or "" when unknown/invalid. */
export function formatLimitReset(resetsAt: string | null | undefined, timeZone?: string): string {
  if (!resetsAt) return "";
  const date = new Date(resetsAt);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return new Intl.DateTimeFormat("en-US", {
      weekday: "long",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      ...(timeZone ? { timeZone } : {}),
    }).format(date);
  } catch {
    return "";
  }
}

export function limitWallForReason(
  reason: string | null | undefined,
  options: { info?: LimitWallInfo | null; isGuest?: boolean; timeZone?: string } = {},
): LimitWallModel | null {
  const { info, isGuest = false, timeZone } = options;
  const cta: LimitWallCta = isGuest ? "create_account" : "upgrade";
  const ctaLabel = isGuest ? "Create an account" : "Upgrade to Pro";

  if (reason === "weekly_limit_reached") {
    const limit = typeof info?.limit === "number" && info.limit > 0 ? Math.floor(info.limit) : null;
    const resets = formatLimitReset(info?.resets_at, timeZone);
    return {
      reason,
      title: limit ? `You've used your ${limit} free trade checks this week` : "You've used your free trade checks this week",
      body: resets
        ? `Free accounts get a limited number of Trade Analyzer checks each week. Your allowance resets ${resets}.`
        : "Free accounts get a limited number of Trade Analyzer checks each week. Your allowance resets at the start of next week (Monday, UTC).",
      proLine: "Pro removes the weekly cap, so you can grade every offer before the deadline.",
      cta,
      ctaLabel,
    };
  }
  if (reason === "premium_required") {
    return {
      reason,
      title: "This is a Pro feature",
      body: "Your Free plan doesn't include this one.",
      proLine: "Pro unlocks it, along with unlimited Trade Analyzer checks.",
      cta,
      ctaLabel,
    };
  }
  return null;
}
