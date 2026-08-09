# Premium Conversion Audit + Intent-Based Upgrade Flow (#225)

Baseline: main after #224 (`de7b0dd84dee96311febdb907c3010fa441d227b`).

## Philosophy

- Guests get value first; free signup sells continuity (#224).
- Premium sells **deeper capability on workflows the user already understands**.
- Upgrade CTAs appear at intent moments only — not as page chrome.
- Experimental features stay flagged; they are **not** sold as included-by-default Premium.

## Canonical Free vs Premium

| Free account | Premium |
| --- | --- |
| Save league / resume setup | More next moves |
| Basic personalized Game Plan | Full League Pulse |
| Core browsing (roster, League Overview, PQV core) | Full trade board + return search |
| Continuity across sessions | Full waiver board + FAAB shortlist |
| Session What Changed | Advanced roster / Deep Analysis / bench insulation |

## Canonical value proposition

**Headline:** Go deeper on the decisions that matter  
**Body:** Premium expands the same Game Plan, Trade Hub, Waivers, and My Team workflows you already use — more moves, fuller boards, and deeper roster analysis.

## Canonical CTAs

| Role | Copy |
| --- | --- |
| Primary (locks / profile / contextual) | Upgrade to Premium |
| Secondary | See what Premium includes |
| Checkout (Premium page only) | Start Founder Premium checkout |
| Premium account profile | Manage Premium |

## Locked-state primitive

`premium.premium_lock_html` / `app.render_premium_lock`:

1. Feature badge name  
2. Title (what it does)  
3. Body (why it matters)  
4. “Included with Premium”  
5. One button: **Upgrade to Premium** → intent capture → Premium page (auth first when guest)

No blurred fake content. Useful Free previews stay visible above the lock.

## Checkout entry / intent

One entry: `premium_page.render_premium_page` → `stripe_billing.create_checkout_session` **only after** explicit checkout click.

Intent payload (`_premium_checkout_intent`): interval, feature (attribution token), surface, route, return_route, league_id.

Guest path: capture intent → free auth dialog (`surface=premium_checkout`) → `mark_resume_checkout_after_auth` → Premium page notice → user clicks checkout (no auto Stripe session).

## Billing return

| Flag | Behavior |
| --- | --- |
| success | Clear entitlement memo → force profile refresh → refresh entitlement → success copy; events `checkout_completed` / `premium_checkout_completed` / `premium_entitlement_activated` when Free→Premium |
| cancel | Calm cancel copy; `premium_checkout_cancelled` (not subscription-cancel) |

## Analytics (allowlisted)

`premium_gate_seen` → `premium_cta_clicked` → `checkout_started` / `premium_checkout_started` → `checkout_completed` / `premium_checkout_completed` → `premium_entitlement_activated`  
Cancel: `premium_checkout_cancelled`

Safe props: surface / `prompt_surface`, `item_kind` (attribution), route, account_state, entitlement, league_id, interval, billing_flag. No email / username / Stripe ids.

Attribution tokens: `trade_depth`, `waiver_depth`, `deep_analysis`, `league_pulse`, `more_next_moves`, `decision_memory`, `gm_targets`, `general_premium_page`.

## Experimental (not graduated)

Decision Memory, GM Targets, Share Recommendation — listed under “Experimental when enabled” on Premium page; still require Ops flags. Not in `PREMIUM_INCLUDED_NOW`.

## Performance

- Opening Premium lock/page does not create Stripe sessions.
- Entitlement memo cleared only on billing success / activation path.
- Does not invalidate Game Plan / trade caches when a Premium modal opens.
- Founder checkout uses `on_click` for guest auth / intent (no extra `st.rerun`).
- Explicit rerun budget raised 42 → 43 to match post-#224 guest conversion inventory (no new premium_page rerun).

## Rollback boundary

Revert this PR’s presentation, intent helpers, analytics allowlist, and tests only. Does not change Stripe product ids, football logic, or experiment graduation.
