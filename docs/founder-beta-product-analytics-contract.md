# Launch Analytics Foundation Contract

> **Update (storage migration):** Persistence is now the durable Supabase
> table `analytics_events` (`docs/supabase_analytics_events.sql`),
> write-through from `track_event` on a background thread (never blocks the
> caller) and read-through for Founder Analytics
> (`modules.launch_analytics.read_events_with_source`). The local JSONL file
> below is unchanged in every other respect and remains a fail-open
> cache/fallback: it is still written on every event, and every read path
> falls back to it automatically when Supabase is unconfigured or
> unreachable. Event taxonomy, privacy model, and everything else in this
> contract are unchanged — this was a storage-backend migration only.

| Field | Value |
| --- | --- |
| Module | `modules/launch_analytics.py` (canonical owner) |
| Kill switch | `DYNASTYGM_LAUNCH_ANALYTICS=1` (default **off**) |
| Environment stamp | `DYNASTYGM_ANALYTICS_ENV` or auto: `production` / `development` / `test` |
| Persistence | Supabase `analytics_events` (durable, cross-instance) + local JSONL fallback/cache (`data/launch_analytics.jsonl`) |
| Retention | **120 days** raw events (`prune_expired_events`, JSONL side; no automatic prune on the Supabase table yet — see `docs/supabase_analytics_events.sql`) |
| Event envelope version | `event_version: 2` |
| Provider decision | **No new external vendor** — extend the existing owner with durable Supabase storage + Founder Ops |

## Architecture map

```
UI / app.py / feature modules
        │
        ▼
modules/launch_analytics.py   ← ONLY application analytics interface
  track_event / track_page_view / track_feature_use
  track_error / track_performance / track_session_started
        │
        ├──────────────────────────────┐
        ▼                              ▼
JSONL append (fail-soft, locked)   Supabase analytics_events insert
  — cache/fallback, unchanged        (background thread, best-effort,
                                       service-role — see
                                       docs/supabase_analytics_events.sql)
        │                              │
        └──────────────┬───────────────┘
                        ▼
        read_events_with_source (Supabase-first,
        JSONL fallback on outage/misconfig)
                        │
                        ▼
        Founder Ops read models
          funnel_summary · retention_summary
          feature_adoption_summary · health_summary
```

No route imports a vendor SDK. Provider adapter (Supabase + JSONL fallback) stays behind this owner.

## Provider decision

| Option | Verdict |
| --- | --- |
| Supabase `analytics_events` + JSONL fallback + Founder Ops | **Chosen** — durable, survives redeploys/restarts, readable cross-instance; JSONL remains the fail-open cache |
| PostHog / Amplitude / Mixpanel / GA | Not introduced — privacy, Streamlit rerun semantics, and cost complexity outweigh benefit before product-market proof |
| Supabase analytics tables | ~~Deferred~~ **Implemented** — see `docs/supabase_analytics_events.sql`. Service-role only; no per-user RLS (events include anonymous/guest sessions and Founder Analytics reads across every account) |

**Rationale:** The repo already had a privacy-conscious, fail-soft, kill-switched analytics owner. This migration gives it durable, cross-instance storage without a second vendor, while keeping the local JSONL as an unconditional fallback so an outage never breaks tracking. At ~10k+ DAU, still plan a proper warehouse — this table's read path is bounded the same way the old JSONL path was (see `VOLUME_MODEL` in `modules/launch_analytics.py`).

## Privacy model — must NOT track

Forbidden in analytics payloads:

- Supabase / auth tokens, cookies, passwords
- Email (unless a future explicit opt-in identity product — **not** this system)
- Raw roster contents, player lists, trade contents
- Private league names, Sleeper usernames
- Arbitrary user-entered text / freeform messages
- Full exception stacks, config secrets, Stripe secrets
- Raw provider response bodies

### Pseudonymous identifiers

| Key | Construction |
| --- | --- |
| `session_key` / `anon_id` | `anon_` + random hex per Streamlit session |
| `user_key` / `account_hash` | `acct_` + SHA-256(`dynastygm-analytics:{user_uuid}`)[:16] |
| `league_key` | `lg_` + SHA-256(`dynastygm-league:{league_id}`)[:16] |

Raw `league_id` may be passed into `build_context_props` but is hashed before persistence.

### Retention / privacy assumptions

- Raw JSONL retained **120 days**, then pruned
- Host-local store (single Render instance) — not a cross-region warehouse
- Founder Ops access requires `DYNASTYGM_FOUNDER_OPS`
- Analytics outage never blocks render

## Event envelope

```json
{
  "event": "dashboard_reached",
  "event_version": 2,
  "ts": 1710000000.0,
  "build": "<git sha>",
  "environment": "production",
  "session_key": "anon_…",
  "anon_id": "anon_…",
  "user_key": "acct_…",
  "account_hash": "acct_…",
  "props": {
    "account_state": "authenticated",
    "entitlement": "free",
    "league_key": "lg_…",
    "route": "dashboard",
    "device_class": "desktop",
    "source_surface": "destination_navigation"
  }
}
```

Optional props (allowlisted): `latency_ms`, `latency_bucket`, `cache_status`, `provider`, `result`, `feature`, `error_class`, `error_fingerprint`, league-format metadata (`league_format`, `scoring`, `qb_type`, `team_count`, `te_premium`).

## Taxonomy (stable allowlist)

Session: `session_started`, `session_restored`, `session_usable`
Navigation: `landing_viewed`, `page_view`, CTAs, `pricing_viewed`
Onboarding: signup/login/guest + `league_import_*`
Dashboard / Game Plan: `dashboard_reached`, `first_game_plan_seen`, `game_plan_item_opened`, `deep_analysis_opened`
GM Orb: `gm_orb_opened`, `gm_destination_selected`
Surfaces: My Team, Trade, Waivers, Draft, Live Draft, Explorer (`players_opened`), News, Alerts
Premium: paywall → checkout → entitlement
Errors: `application_error`, `provider_error`, `route_error`, `degraded_mode_entered`
Performance: `startup_complete`, `dashboard_first_useful`, `route_ready`, `package_build`, `provider_call`, `cache_lookup`

Requested alternate names are remapped via `LEGACY_EVENT_ALIASES` (e.g. `dashboard_viewed` → `dashboard_reached`).

## Streamlit rerun dedupe

| Mechanism | Behavior |
| --- | --- |
| `_SESSION_EMITTED` + `once_key` | Process-local once markers |
| `track_route_opened` / `track_page_view` | Only when `changed=True`; key `scope:league_key:route` |
| `track_session_started` | Session flag + once marker |
| `track_error` | Deduped by `error_fingerprint` per session |
| `track_performance` | Once per milestone/route |
| Logout / account switch | `clear_analytics_session` |

**Proof target:** one user action → one intended event (not one event per script rerun).

## Founder Labs analytics surface

Read-only UI in Founder Labs (`modules/founder_analytics.py` + `founder_analytics_ui.py`).
Authorization is the Labs contract (signed-in + kill switch + server-issued claims).
There is **no customer route** for analytics.

Internal `founder_labs` / `founder_ops` traffic is excluded from `track_event`.

Storage remains host-local JSONL. The UI must label counts as this-instance only.
Do not treat funnel conversion percentages as product-wide rates.

`DYNASTYGM_LAUNCH_ANALYTICS` stays **default off**. Enabling it is a manual Render
env change on `FANTASYGMLAB`, not a code default.

## Active user & meaningful engagement

- **Active user:** distinct `user_key` / `account_hash` / `anon_id` with ≥1 event in the window
- **Meaningful active user:** identity with ≥1 event in `MEANINGFUL_ENGAGEMENT_EVENTS` (feature opens/actions, not background reruns)
- Background Streamlit reruns must not increment engagement without a new `once_key` action

## Funnels

| Funnel | Transition events |
| --- | --- |
| A. Visitor → usable | `landing_viewed` / `session_started` → auth → `league_import_completed` → `dashboard_reached` (+ `session_usable` / `dashboard_first_useful`) |
| B. Returning activation | `session_restored` → `dashboard_reached` → meaningful feature event |
| C. Premium | `premium_viewed` → `checkout_started` → `checkout_completed` → `premium_entitlement_activated` |
| D. Game Plan | `dashboard_reached` → `first_game_plan_seen` → `game_plan_item_opened` → destination route |
| E. Alerts | `notification_center_opened` → `notification_item_opened` → related surface route |

## Retention

Computed by `retention_summary()`:

- DAU / WAU / MAU
- D1 / D7 / D30 rolling retention (% of users active on day T−N also active on day T)
- sessions/user, meaningful actions/session

Requires kill switch **on** in production and durable JSONL on the serving host.

## Founder dashboard spec (Founder Ops)

| View | Source |
| --- | --- |
| OVERVIEW | `retention_summary` + signup/league/dashboard/checkout counts |
| FEATURES | `feature_adoption_summary` (users/sessions/views/meaningful) |
| FUNNEL | `funnel_summary` step conversions |
| HEALTH | `health_summary` error rate, p50/p90/p95 latency, cache hit, degraded-mode |
| RELEASE | `errors_by_build` + performance rows stamped with `build` SHA |

Metric formulas live in `launch_analytics.py` (`retention_summary`, `health_summary`, `feature_adoption_summary`).

## Cost / volume model

| Scale | Est. events/day | Guidance |
| --- | --- | --- |
| ~12 events/session, ~18/DAU | — | Expected |
| 100 DAU | ~1.8k | JSONL fine |
| 1k DAU | ~18k | JSONL fine single-host |
| 10k DAU | ~180k | Plan warehouse drain |
| 100k DAU | ~1.8M | External warehouse required |

High-volume candidates (keep once-keyed): route opens, session start, performance milestones. Do **not** emit hover/mouse noise or full startup waterfalls into product analytics.

## Ops activation

1. Set Render `DYNASTYGM_LAUNCH_ANALYTICS=1`
2. Confirm Founder Ops analytics summary (overview / features / health / funnel)
3. Optionally prune via Founder Ops “Prune analytics retention”

## Limitations / still missing before scale

- Multi-instance aggregation (host-local JSONL)
- No third-party dashboard charts beyond Founder Ops JSON views
- Device class requires explicit `set_device_class` when viewport known
- Some deep action events (waiver claim clicks, trade accept) remain future wires
- Durable warehouse export not in this PR

## Rollback

Unset kill switch or revert the landing commit. Product UX unchanged when analytics is off.
