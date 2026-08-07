# Founder Beta Product Analytics & Funnel Instrumentation

| Field | Value |
| --- | --- |
| Baseline | `49780ad7b1c3d3c5b07d899811b876ee58d7dccc` (post #163) |
| Module | `modules/launch_analytics.py` (extended — not a parallel system) |
| Kill switch | `DYNASTYGM_LAUNCH_ANALYTICS=1` (default **off**) |
| Persistence | Local JSONL (`data/launch_analytics.jsonl`) |
| Retention | **120 days** raw events (`prune_expired_events`) |

## Purpose

Answer Founder Beta product questions without guessing:

- How many people signed up and imported a league?
- Who reached Dashboard and which core workflows they used?
- Where Premium conversion happens?
- Whether Decision Memory / GM Targets see real usage?

Analytics **observes** behavior. It never changes football logic, entitlements, Stripe, or Trust.

## Event taxonomy

Canonical allowlist in `TRACKED_EVENTS`. Unknown names are rejected.

### Core funnel

`landing_viewed`, `signup_started`, `signup_completed`, `login_completed`,
`league_import_started`, `league_import_completed`, `dashboard_reached`,
`first_game_plan_seen`, `trade_hub_opened`, `trade_review_opened`, `pqv_opened`,
`waivers_opened`, `my_team_opened`, `league_overview_opened`,
`notification_center_opened`, `feedback_submitted`

### Premium funnel

`premium_viewed`, `premium_cta_clicked`, `checkout_started`, `checkout_completed`,
`portal_opened`, `subscription_cancel_requested`

Checkout completion is **not** entitlement truth — Stripe/Supabase remain authoritative.

### Experimental usage

`decision_memory_viewed`, `decision_memory_event_opened`,
`gm_targets_viewed`, `gm_target_added`, `gm_target_removed`,
`game_plan_item_opened`, `notification_item_opened`

Events fire on meaningful actions (opens/clicks/mutations), not mere widget presence
where that would spam Streamlit reruns.

## Payload shape

```json
{
  "event": "dashboard_reached",
  "ts": 1710000000.0,
  "build": "...",
  "anon_id": "anon_…",
  "account_hash": "acct_…",
  "props": {
    "account_state": "authenticated",
    "entitlement": "free",
    "league_id": "…",
    "route": "dashboard",
    "source_surface": "destination_navigation"
  }
}
```

Legacy names (`landing_visit`, `account_created`, …) are remapped when reading counts.

## Privacy model

- No emails, tokens, cookies, passwords, or freeform messages
- Prop keys allowlisted; blocked keys stripped
- Account correlation uses SHA-256 hash of user UUID (`account_hash`), never email
- Guest journeys use `anon_id` minted per Streamlit session
- JSONL is local Founder Ops evidence — not a public analytics warehouse

## Persistence decision

**Extend existing JSONL launch analytics.** No Supabase analytics table in this PR.

Rationale: lightest reliable Founder Beta path, already wired into Founder Ops,
fail-soft, no service-role in Streamlit, no new RLS surface.

## Kill switch

| State | Behavior |
| --- | --- |
| Off | No writes; product UX unchanged; Founder Ops shows analytics disabled |
| On | Append JSONL; Founder Ops metrics + funnel available |

Also listed in `WEB_APP_CONFIG_KEYS` as `DYNASTYGM_LAUNCH_ANALYTICS`.

## Dedupe strategy

- Process-level `_SESSION_EMITTED` markers (`event:once_key`)
- Route milestones via `track_route_opened` only on real destination entry
  (including first assignment), keyed by `account_or_anon:league:route`
- Clicks/mutations generally emit once per action (no once_key) or with stable keys
- `clear_analytics_session` on logout / account switch clears markers + anon id
- League scope updated via `set_league_scope` without wiping landing dedupe

## Account / league scoping

| Transition | Behavior |
| --- | --- |
| Logout / account switch | `clear_analytics_session` |
| League switch | Update `league_id` on subsequent props; route once_keys include league |
| Restored session | New anon id if cleared; account_hash from restored auth |

## Founder Ops metrics

Read-only summary (View analytics summary):

- landing / signups / logins / leagues imported
- Dashboard reached / Trade Hub opens / PQV opens
- Premium views / checkout starts & completions
- Feedback submissions
- Decision Memory views / GM Targets adds
- Funnel steps + conversion % from prior step

## Funnel definition

Landing → Signup → League Import → Dashboard → Core Feature Use →
Premium View → Checkout Start → Checkout Complete

Core Feature Use aggregates Trade Hub, PQV, Waivers, My Team, Trade Review,
League Overview, Game Plan, notifications, Decision Memory, GM Targets usage.

## Performance

- Non-blocking append under lock; exceptions swallowed
- Not on first-useful / Trade Hub #1 / PQV first-useful critical path
- No extra Streamlit reruns from analytics alone
- Must not raise protobuf budget (no cold-path CSS)

## Retention

Raw JSONL retained **120 days**. Call `prune_expired_events()` from Founder Ops or Ops jobs as needed. Structure supports future day/week return analysis via `anon_id` / `account_hash` + `ts` without shipping cohort UI now.

## Ops activation

1. Set Render `DYNASTYGM_LAUNCH_ANALYTICS=1`
2. Confirm Founder Ops analytics summary is enabled
3. Optionally schedule `prune_expired_events`

## Limitations / future

- Local JSONL is host-local (not cross-instance aggregate on multi-host)
- No full cohort retention UI yet
- `subscription_cancel_requested` currently keyed to billing cancel return flags
- Attribution is step conversion, not multi-touch

## Rollback

Unset kill switch or revert this PR. Product behavior unchanged when analytics is off.
