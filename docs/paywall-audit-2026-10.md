# Paywall circumvention audit, 2026-10

Scope: `services/mobile_api_service.py` (the API behind web-next and mobile), found by reading the routes, not the UI.
Tiers: Free, Pro (`premium.PRO`, stored as raw `premium`), Front Office. Pro and Front Office behave identically here.

## Inventory (what Free gets, where the check lives)

| Surface | Route(s) | Free gets | Check |
|---|---|---|---|
| Trade Hub | `GET /leagues/{id}/trade-hub` | top 2 ideas + server-granted ad bonus, one shared per-user pool | `is_at_least` + `free_tier_ledger` pool (fixed) |
| All Trades | `GET .../all-trades` | same pool | same (fixed; `shown_count` now ignored) |
| Trade Finder | `GET .../trade-finder` | nothing (upsell) | `is_at_least` in route |
| Trade share card | `GET .../trade-hub/{rec}/share-card.png` | only ideas already revealed to them | pool check (fixed) |
| GM Plan | `GET .../gm-plan` | nothing (upsell) | `is_at_least` in route |
| Dashboard | `GET .../dashboard` | first 4 items; Top Trade tile only if it fits the pool | `FREE_DASHBOARD_VISIBLE_ITEMS` + pool (fixed) |
| Portfolio (incl. Today / headline idea) | `GET /portfolio`, `/portfolio/leagues`, `/portfolio/leagues/{id}` | nothing (upsell) | `_portfolio_context` |
| Home leagues-glance | `GET /leagues-glance` | nothing (upsell) | `is_at_least` in route |
| Alerts / briefings | `GET .../alerts` | roster news only; carries no trade ideas | n/a |
| External API | `/v1/external/*`, `/v1/content/feed` | player/news data only, no league or trade data | service token |
| Manager Tendencies | `.../managers/tendencies`, `.../{roster}/tendencies` | upsell | `_manager_tendencies_gate` |
| Live Draft | `.../live-draft`, `.../live-draft/{id}` | discovery only; state withheld | `is_at_least` |
| Live Draft trade evaluator | `.../live-draft/{id}/trade-evaluator` GET/POST | nothing (was open) | `_manager_tendencies_gate` (fixed) |
| Waivers | `.../waivers` | pool; Priority Adds / FAAB guidance withheld | `is_at_least` |
| GM Targets (add) | `POST .../gm-targets` | capped count | `is_at_least` |
| Saved leagues | `POST /leagues/save` | 1 league (`MAX_LEAGUES_FREE`) | `saved_leagues.is_at_cap` |
| Trade Analyzer | `POST .../trade-analyzer` | 3 evaluations/week | web only before; now server-side (fixed) |
| Player exposure | not present in the API yet | n/a | n/a |
| Playoff Odds, Team Rankings, Draft Center, My Team Needs, Team Situation, College Scouting | various | full data (ungated) | none, see Recommended |

## Leaks found and fixed (all server-side)

1. **Forged ad unlocks.** `ad_unlocks` came straight from the query string: `trade-hub?ad_unlocks=3` returned 8 ideas to a Free user. Now the server owns the count (`free_tier_ledger`): the client number is only a hint that can raise the stored count by 1 per 10 s, max 3 per UTC day.
2. **Per-board allowance.** Each (league, strategy, lens, filters) board was gated separately, so switching strategy or lens yielded 2 new ideas each time. Now one per-user pool of revealed idea ids per UTC day (Redis), shared by every page.
3. **`shown_count` reset on All Trades.** The cap was a client-reported tally, so `shown_count=0` on each page reset it. Now ignored; All Trades draws from the same pool as Trade Hub.
4. **Dashboard headline idea** was outside any pool. It is now claimed from the same pool, or withheld.
5. **Share card** rendered a branded PNG for any idea on the full unredacted board, including hidden ones. Free can now share only ideas it was shown.
6. **Free league cap on the read side.** `save_league` enforced the cap, but every roster-resolved route resolved the caller's roster in any Sleeper league they belong to, saved or not. A Free user could read Trade Hub, Dashboard and All Trades for every league. `_resolve_my_roster` now allows only saved leagues, plus unsaved ones while the account has spare cap (tracked server-side), and returns reason `free_league_cap`.
7. **Live Draft trade evaluator** (GET options and POST verdict) was open to Free although Live Draft is locked. Now Pro-only.
8. **Weekly Trade Analyzer limit** (3/week) existed only in the Streamlit app. Now enforced on `POST .../trade-analyzer` (reason `weekly_limit_reached`, HTTP 200, same shape as other not-ready states).

Checked and not leaking: ESPN import and `/leagues/save` use the same `is_at_cap`; the rollover migration (`migrate_saved_league`) moves one row (upsert then delete), it never adds a league; cache keys: trade-idea records are cached unfiltered and gated after the cache, profile and saved-league caches are keyed by user id, and the web share-card cache is keyed by the caller's bearer token.

## Free league cap closed on every league-scoped endpoint (follow-up)

Two leaks remained after item 6: (Gap 1) a Free account with no saved league could claim one unsaved league, and the claim was never released when a league was later saved or removed (and the saved-leagues cache was only dropped on ESPN saves, so a Sleeper save left a stale "zero saved" view for the cache TTL); (Gap 2) league endpoints that never resolve "my roster" had no league gate, so a Free account could read any number of leagues through them.

Fix, one authority: `require_league_access` (FastAPI dependency, drop-in for `resolve_league_path_id`) backed by `_league_access_allowed` -> `_free_league_allowed` (also used by `_resolve_my_roster`). Allowed if Pro/Front Office/trialing (a trial reads as entitlement premium); for Free: a saved league, or, only while zero leagues are saved, the single league claimed in `free_tier_ledger`. Save and remove (`/v1/leagues/save`, `DELETE .../save`) now drop the saved-leagues cache and call `free_tier_ledger.release_league_claims`, so a saved league replaces the claim. Locked answer: HTTP 200 `{ok, reason: "free_league_cap", league_locked: true, league_id, is_premium: false, upsell}`, raised before the route body (no data, no compute). Cost: the same cached profile + saved-leagues reads as before, memoised per request; Pro needs only the profile.

Gated by the dependency: `users`, `rosters`, `team-profiles`, `team-rankings`, `playoff-odds`, `draft-center`, `draft-picks`, `live-draft`, `live-draft/{id}`, `live-draft/{id}/trade-evaluator` (GET/POST), `rankings`, `idp/values`, `players/{id}/rank`, `recap`, `history`, `storylines`, `managers/tendencies`, `managers/{id}/tendencies`, `guess-the-player/leaderboard`, `matchup/what-if`. Already gated through `_resolve_my_roster` (own response shape, same reason): my-roster, trade-analyzer, alerts, dashboard, gm-plan, my-team, keepers, guillotine, my-team-needs, matchup, waivers, trade-hub (+share card), trade-finder, all-trades.

Deliberately open: `GET /v1/leagues/{id}` and `warmup-status` (metadata used while adding a league), preview/import endpoints (external ids), user-owned preference rows (gm-stance, team-stance, gm-targets, league-type, keeper-settings, alerts/read, trade-outcomes), `/v1/external/*`, public content. Remaining stricter-reading caveats: fails open if the profile or saved-leagues read errors; a Free user with no saved league can still rotate their one claim by saving then removing a league (concurrent cap still holds).

Clients: `lib/api.ts` (web and mobile) turns the locked payload into an ApiError with a fixed message and the shared ErrorState renders the shared locked card (PremiumUpsellCard / PremiumLock) for it.

Tests: `tests/test_paywall_league_cap.py` (every gated endpoint: Free A cannot read B, Free with none gets exactly one, Pro/Front Office/trialing unaffected, claim replaced on save, no compute when locked, add-league flows open).

## Degradation for shipped builds

Response shapes are unchanged. Free responses carry fewer or zero ideas, `ad_unlocks_applied` now reports the server's count, and new `reason` values (`free_league_cap`, `weekly_limit_reached`, `premium_required`) are 200s like the existing not-ready reasons.

## Stricter readings chosen (owner can relax)

- Pool resets daily (UTC), not per session; constant is in `modules/free_tier_ledger.py`.
- If a Free user's pool is full of ideas that later change, they see no new ideas until the next UTC day.
- Free with zero saved leagues may use exactly one unsaved league (so first-time import works).
- Dashboard drops the trade tile rather than blurring it.
- Weekly analyzer evaluation is consumed once the roster resolves, even if the verdict later fails.

## Recommended, not changed (product intent unclear)

- **Ad unlock verification.** Without rewarded-ad server-side verification (AdMob SSV) a determined client can still earn 3 unlocks per day by claiming them. Real fix: a signed ad-callback endpoint.
- **College Scouting** is Pro on web but ungated on the API (`/scouting/*`). Playoff Odds, Team Rankings detail, Draft Center, My Team strategy/needs are ungated; decide which are meant to be Pro.
- **Database-level cap.** `saved_leagues` and `user_settings` are writable by the user's own token under RLS, so a direct Supabase client can bypass the app-level 1-league cap. Add a Postgres trigger enforcing the cap by entitlement.
- Pool/ad counters degrade to a per-process memory ledger if Redis is down (cap still holds per worker).

## Verification

Local only: every fix has a regression test in `tests/test_paywall_leaks.py` (real FastAPI TestClient, fake auth, Free profile) that fails on `origin/main` and passes here. Not verified against production as a Free user (no account), real Redis, or real Sleeper/Supabase.
