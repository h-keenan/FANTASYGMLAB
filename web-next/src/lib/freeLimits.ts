/**
 * "Free: X of Y" notes, shown BEFORE a Free account hits a cap.
 *
 * Pure text/decision logic shared by web and mobile (mobile/src/lib/
 * freeLimits.ts is byte-identical; a web test keeps them in sync). It never
 * carries a limit of its own: every number comes from the API response that
 * the backend builds from the real constants (modules.gm_targets
 * MAX_TARGETS_FREE, modules.trade_hub_presentation FREE_VISIBLE_IDEAS,
 * services.mobile_api_service FREE_DASHBOARD_VISIBLE_ITEMS,
 * modules.saved_leagues MAX_LEAGUES_FREE via /v1/me league_cap). When the
 * server did not send a limit, or the account is Premium or not yet known,
 * there is no note: better silent than a wrong number.
 */

export type FreeLimitCta = "create_account" | "upgrade";

export interface FreeLimitNoteModel {
  text: string;
  /** True when the user is already at (or past) the limit. */
  atLimit: boolean;
  /** Guests may not buy, so they are asked to create an account first. */
  cta: FreeLimitCta;
  ctaLabel: string;
}

export interface FreeLimitInput {
  /** Plural noun, e.g. "GM Targets", "trade ideas". */
  noun: string;
  /** The server's Free limit. Missing/non-positive: no note. */
  limit: number | null | undefined;
  /** Strictly `false` shows a note; `true`/unknown (null/undefined) does not. */
  isPremium: boolean | null | undefined;
  isGuest?: boolean;
  /** "cap": things the user saves (used of limit). "window": a list the
   * server truncates for Free (shows `limit` of `total`). */
  kind: "cap" | "window";
  /** cap: how many the user has used. */
  used?: number;
  /** window: how many exist in total (before truncation). */
  total?: number;
  /** window: how many are shown right now (defaults to `limit`; can be more
   * after an ad unlock). */
  shown?: number;
}

export function freeLimitNote(input: FreeLimitInput): FreeLimitNoteModel | null {
  const { noun, limit, isPremium, isGuest = false, kind } = input;
  if (isPremium !== false) return null;
  if (typeof limit !== "number" || !Number.isFinite(limit) || limit <= 0) return null;

  let text: string;
  let atLimit: boolean;
  if (kind === "cap") {
    const used = Math.max(0, Math.floor(input.used ?? 0));
    text = `Free: ${used} of ${limit} ${noun}`;
    atLimit = used >= limit;
  } else {
    const total = typeof input.total === "number" && input.total >= 0 ? Math.floor(input.total) : null;
    if (total !== null && total > limit) {
      const shown = typeof input.shown === "number" && input.shown >= 0 ? Math.floor(input.shown) : limit;
      text = `Free: showing ${shown} of ${total} ${noun}`;
      atLimit = true;
    } else {
      text = `Free: up to ${limit} ${noun}`;
      atLimit = false;
    }
  }
  return isGuest
    ? { text, atLimit, cta: "create_account", ctaLabel: "Create an account" }
    : { text, atLimit, cta: "upgrade", ctaLabel: "Upgrade" };
}
