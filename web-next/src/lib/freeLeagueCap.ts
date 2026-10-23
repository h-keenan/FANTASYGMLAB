/**
 * Free-tier league cap, client side. The API answers a league-scoped request
 * for a league outside the Free allowance with HTTP 200 and
 * `{ league_locked: true, reason: "free_league_cap", upsell }` (no data).
 * `lib/api.ts` turns that into an ApiError carrying this exact message, and the
 * shared ErrorState renders the locked upgrade card for it instead of a
 * generic failure. Mirrors mobile/src/lib/freeLeagueCap.ts.
 */
export const FREE_LEAGUE_CAP_MESSAGE =
  "Your Free plan includes one league, and this isn't it. Upgrade to use all of your leagues.";

export function isFreeLeagueLockedBody(body: unknown): boolean {
  return (
    !!body &&
    typeof body === "object" &&
    (body as { league_locked?: unknown }).league_locked === true &&
    (body as { reason?: unknown }).reason === "free_league_cap"
  );
}
