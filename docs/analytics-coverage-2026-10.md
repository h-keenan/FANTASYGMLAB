# Analytics coverage audit (2026-10)

## Pipeline

client -> `POST /v1/analytics/event` (`services/mobile_api_service.record_analytics_event`, optional bearer) ->
`modules/launch_analytics.track_event` (allowlist `TRACKED_EVENTS`, prop allowlist `ALLOWED_PROP_KEYS`, blocked keys,
internal-traffic exclusion, account/league hashing) -> Supabase `analytics_events` (durable) with host-local JSONL fallback ->
`modules/founder_analytics.build_report` -> `GET /v1/founder/analytics` -> `/founder-analytics` (`FounderAnalyticsContent`).

Server write switch: `DYNASTYGM_LAUNCH_ANALYTICS` (default OFF; must be on in production for any client's events to be stored).
Unknown event names and non-allowlisted props are silently dropped server-side, so every new event name must be in `TRACKED_EVENTS`.

## Taxonomy (additions in this change in bold)

- Navigation: `page_view` (route), `landing_viewed`, `*_opened` surface events, **`session_started` (mobile app open/foreground)**.
- Auth/onboarding/league connect: `signup_*`, `login_completed`, `league_import_*`, `sleeper_connected`.
- Premium: `premium_viewed`, `premium_cta_clicked`, `checkout_started` (now fired from the web paywall), `premium_gate_seen`, `checkout_completed`, `premium_entitlement_activated`.
- **`feature_use`**: generic cross-platform interaction. Props: `feature` (snake_case id), `action` (opened, viewed, filter_changed, shared, evaluated, gate_seen, upsell_tapped, ...), optional `tier` (`free`/`pro`), `platform` (`web`/`ios`/`android`), `item_kind`, `result`, `source_surface`.
- Errors: `application_error` / `route_error` / `provider_error` with `error_class`, `route`, `reason` (`status_NNN`). Previously only fired server-side from the Streamlit app.
- Platform: server defaults a missing/unknown `platform` to `web`; mobile sends `ios`/`android`.

## Coverage

| Surface | Web before | Web now | Mobile before | Mobile now (when enabled) |
|---|---|---|---|---|
| App open / session | none | page_view | none | `session_started` (open + foreground) |
| Screen / page views | page_view + `*_opened` | same (id segments now stripped from routes) | none | `page_view` route `mobile/<ScreenName>` on every navigation |
| Sign in / sign up | landing + signup events | same | none | `feature_use auth sign_in/sign_up/sign_in_apple` (+result) |
| League connect | league_import_* | same | none | `feature_use league_connect completed/failed` (sleeper/espn) |
| Paywall / subscription | none on web client | `premium_viewed`, `premium_cta_clicked`, `checkout_started` (tier, interval) | none | `feature_use paywall viewed/purchase_started/purchase_finished/restore` |
| Locked card views / upsell taps | none | `feature_use <gated feature> gate_seen / upsell_tapped` (tier=free) via `PremiumUpsellCard`, tendencies link | none | same via `PremiumLock`, tendencies link |
| Trade Analyzer evaluate / share | opened only | `trade_analyzer evaluated/shared` | none | same |
| Matchup swap planner | none | `matchup_swap_planner opened/swap_applied` | none | same |
| Percentile Explorer | none | `percentile_explorer opened/pool_changed/compare_picked` | none | `opened/pool_changed` |
| Manager Tendencies chips | none | `manager_tendencies viewed (pro)/gate_seen/upsell_tapped (free)` | none | same |
| Player exposure | none | `player_exposure viewed` (tier) + gate events (`exposure`) | none | same |
| Trade Hub filters | none | `trade_hub_filters filter_changed` | none | same |
| Share cards | none | `share_card shared` (player, trade idea) | none | `share_card shared` (trade) |
| Alerts dropdown | none | `alerts_dropdown opened` | n/a | screen view only |
| "Did this trade happen?" | none | `trade_outcome_prompt shown/answered/dismissed` | none | `answered` |
| Onboarding funnel | page_view only | `feature_use onboarding step_viewed/back/skipped/experience_selected/completed` (carousel + paywall step) | none | same from `OnboardingScreen` (dark until analytics enabled) |
| Waivers | `waivers_opened` | same | none | screen view |
| Errors | console only | `application_error` (error boundary), `route_error` (shared `ErrorState`), `provider_error` (5xx / network failures in `lib/api.ts`); max 5/min/tab, de-duplicated | none | none (recommendation) |
| Founder dashboard | feature adoption, decision engagement, funnel | + platform split and `feature_use` table (platform + free/pro columns) | n/a | n/a |

## Onboarding funnel

`feature_use` with `feature=onboarding`. Actions: `step_viewed` (once per step per session, deduped client-side), `back`, `skipped`, `experience_selected`, `completed`. Props (all fixed ids, added to `ALLOWED_PROP_KEYS`): `step` (`gameplan`, `tradehub`, `matchup`, `planner`, `pqv`, `playoff`, `tendencies`, `waivers`, `connect`, `level`, web-only `paywall`), `step_index`, `experience` (`new` = beginner, `expert` = advanced). `connect_started` is not emitted: the Connect step is informational (the actual Sleeper/ESPN connect is already `league_connect`). The founder page shows an "Onboarding funnel" section (users per step, drop-off vs previous step, skip rate, experience split, completion rate) from `founder_analytics._onboarding_funnel`; it is omitted entirely when no onboarding events are stored. Users are distinct account/anon ids; rates are among users who viewed at least one step.

## Gaps remaining

- Server-side `entitlement` prop is always `free` for these events (no profile in the request shim); use the client `tier` prop instead. A server-side lookup would be a follow-up.
- `page_view` is de-duplicated per user+route for the life of the server process, so it counts distinct users per screen, not total views. Use `feature_use` for repeat interactions.
- Mobile error/crash reporting is not added; mobile `Alerts`/`Waivers` have screen views only.
- Free-vs-Pro conversion by feature is read as `gate_seen` -> `upsell_tapped` -> `premium_cta_clicked` -> `checkout_started` for a feature; there is no attribution carried from the gate into checkout yet.
- `checkout_completed` / `premium_entitlement_activated` still depend on the server webhook path being wired to the same log.

## Privacy

Identifiers sent: a random per-install `anon_<hex16>` id (localStorage on web, AsyncStorage on mobile) and, when signed in, the Supabase bearer token, which the server verifies and immediately reduces to a salted hash (`account_hash`); the raw user id is not stored. League ids are sent only as `league_id` and stored as a hash (`league_key`); other prop keys outside the allowlist are dropped, and keys such as email, token, player_name, league_name, roster, trade, query, stack are explicitly blocked. The new clients never put emails, tokens, names, free text, or player/league names in events; error events carry the JS error constructor name or an HTTP status bucket, never messages, stacks or URLs. Routes have long/numeric path segments replaced with `:id` (web) and mobile sends screen names only.

Legal copy today (`modules/legal_pages.py`, `mobile/src/data/legalContent.json`, "First-party product analytics"): "FantasyDesk also collects a first-party, pseudonymous analytics signal -- for example, which screens or features are used and basic session timing -- to diagnose problems and improve the product." It also states no third-party advertising, analytics or session-recording service is used. Mobile events fit that description, so no privacy-policy text change is needed.

**App Store disclosure (owner decision, do not change in review):** sending usage events from the iOS app is "Data collection" in App Privacy terms: Usage Data -> Product Interaction (and an identifier, Device ID or User ID, since the anon id and account hash are linkable to a user), purpose Analytics, linked to the user when signed in. If the current App Privacy answers do not already declare Analytics/Product Interaction, they must be updated before mobile analytics is enabled. Because of that, mobile analytics ships dark.

## Mobile kill switch

`EXPO_PUBLIC_ANALYTICS_ENABLED` (read in `mobile/src/lib/analytics.ts`) defaults OFF. Only `1/true/yes/on` enables it. When off nothing is queued, stored or sent. To turn on: set the variable in `mobile/.env` / EAS env for the next build (needs a new app build; never from fastlane without approval) and make sure `DYNASTYGM_LAUNCH_ANALYTICS=1` on the API. Events are batched (25 per flush), flushed every 30 s and on background, kept in a persisted queue (200 max, 3-day expiry), and every failure is swallowed.

## Recommendations

- Decide on the App Privacy answers, then enable mobile analytics in a build.
- Add a server-side entitlement lookup so `entitlement` is accurate on every event.
- Add crash/error reporting on mobile (error boundary + `application_error`).
