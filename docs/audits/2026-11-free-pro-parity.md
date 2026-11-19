# Free vs Pro parity audit (2026-11-19)

Scope: every gated surface on web (`web-next/`) and app (`mobile/`) after #2132, #2140, #2142, #2144, #2147, #2155.
Method: read the server gate (`_is_pro_caller`, `premium.is_at_least`, `_sim_is_pro`), the cache keys, and both clients' gate code.
Static review only; no device runs. Out of scope (listed, not touched): billing, Stripe, RevenueCat, purchase code,
and "Front Office folded into Pro" (`premium.canonical_tier` maps `front_office` to Pro; escalated to the owner).

Test pointers: `tests/test_entitlement_matrix.py`, `tests/test_paywall_leaks.py`, `tests/test_sim_game_api.py`, `tests/test_sim_free_season.py`.

## Per-feature tables

"late" means the Free state shows only after a user action.

| Feature | Server gate | Web gate | App gate | Free state | Leaks |
|---|---|---|---|---|---|
| League Activity | none (client-built from free `team-rankings`) | none | none | card, hidden when no highlights | none (free by design) |
| Roles/usage (player card, waivers) | `_project_usage_profile(pro=)`; waivers `display=is_premium`, `usage_locked`, `usage_gate` | `usage_profile.gated` teaser | same | clean teaser | none found |
| Roles in trade ideas | `usage_roles_pro=_is_pro_caller`; `ur=0/1` in the `trade_hub_ideas` key | n/a | n/a | n/a | none; key split verified |
| Role notes in Trade Analyzer | `role_notes` only for Pro | block hidden if empty | same | silently hidden, no teaser | none (UX gap, C3) |
| GM Plan Roles item | whole `/gm-plan` is Pro; Free gets `quiet` + `upsell` before any work | `data.is_premium` upsell | `is_premium === false` upsell | clean | none |
| Playoff odds page | `/playoff-odds` Pro; simulation not run for Free | lock after tapping "Calculate" | lock on open | clean (web late, C5) | see L1 |
| Playoff odds via Games | `/games/season-sim` free by design (#1486), returns every team's odds | "League playoff odds" table | `my_team` only | visible to Free | **L1** |
| Trade Hub / ideas | Free cap via `free_tier_ledger`; share card refuses hidden ideas; tier-split cache key | upsell card | upsell card + ad unlock | clean | none |
| Trade Finder | Pro; Free gets `is_premium:false` + upsell | `!result.is_premium` | `=== false` | late (after a search) | none |
| Multi-team finder | Pro; Free gets `locked`, `idea_count`, no assets; cache per user, projected after | locked card | locked card | clean | none |
| Wrapped (Sim) | `steal`/`trades` cards `locked`, `data: None` for Free; title/sub carry no player data | locked view | locked view | clean; share hidden when locked | none |
| Wrapped (real league) | none, documented in `modules/wrapped_real.py` | n/a | n/a | full deck | by design |
| Draft & Watch | report free; new game goes through `create_game` free-season claim | Pro buttons to `/premium` | Paywall | clean | none |
| Sim free season | `view.paywalled` on `_mutate` writes | paywall card | paywall card | clean | **S1** (fixed) |
| GM Plan | Pro (`/gm-plan`) | upsell | upsell | clean (minor precedence mismatch) | none |
| Draft Center, Scouting, Commissioner, Live Draft, Portfolio, Trade Target, Tendencies | gated server-side before work | upsell | upsell | clean | none |

## Ranked issues

1. **S1 (server gate gap, fixed).** Sim offseason commands (`rookie-draft/start|pick|auto`, `offseason/start-season`) had no `paywalled` check, so a lapsed Pro account paused in a dynasty offseason could keep playing seasons. Fixed with tests.
2. **L1 (leak, escalated).** `GET /v1/leagues/{id}/games/season-sim` returns all teams' playoff and title odds to Free, and web Games renders them as "League playoff odds"; the Playoff Odds screen for the same data is Pro. Needs an owner decision because the Season Simulator baseline shipped free in #1486.
3. **C1 (client).** Track record and prospect "advanced" locks depend on a separate `/me` call; if it fails Free sees a blank. Fix: gate on the response's own locked flag.
4. **C2 (parity, fixed).** Web Trade Finder tests `!result.is_premium`; the app tests `=== false`.
5. **C3.** Role notes hidden with no teaser for Free in Trade Analyzer (both).
6. **C4.** Trade Finder upsell only after a Free user builds a package and searches (both).
7. **C5.** Web Playoff Odds needs a Calculate tap before the Pro lock; app shows it at once.
8. **C6.** App multi-team module has no ESPN guard that web has.
9. **C7.** Trade Hub copy/CTA differs (app ad-unlock, web `/premium`); GM Plan `reason` vs `is_premium` precedence differs; GM Plan catalogue copy says "Pro adds focus areas".
10. **C8.** Sim `preview` not cleared on a null read; watch-report parse failure shows no upsell.
11. **C9.** Player share cards render `usage_trend` with no client check; server withholding for Free not confirmed.
12. **C10.** Red for negative usage states and cold streaks (no-red-verdicts rule).

## Fixes

S1 and C2 ship as separate PRs (see delivery report). Everything else is open or escalated.

## Listed, not touched

Billing, Stripe, RevenueCat, entitlement purchase code, Front Office folded into Pro.
