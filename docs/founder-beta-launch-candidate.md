# Founder Beta Launch Candidate (Production Readiness)

Production break-test and readiness report for FantasyGM Lab Founder Beta.

| Field | Value |
| --- | --- |
| Baseline at branch | `b59976d` (current `main` after PR #115) |
| Prompt baseline note | `80fdef2` was post-#111; this LC includes #112–#115 |
| Scope | Production readiness — no football logic, valuations, rankings, recommendation ordering, Trust math, Stripe behavior, Supabase schema, authentication rules, or business-rule changes |
| Date | 2026-08-05 |

## Launch recommendation

**Ready after listed manual tasks**

Automated product, UI, Trust integrity, packaging, security-static, analytics wiring,
performance budget, and Chromium checks pass on current `main`.

FantasyGM Lab is **not cleared to charge real money** until the Ops P0 checklist
below is completed on production hosts.

## What this PR fixed (code)

| Issue | Fix |
| --- | --- |
| 5 of 9 launch analytics events never emitted | Wired `account_created`, `league_imported`, `trade_hub_opened`, `player_quick_view_opened`, `premium_checkout_completed` with session/once dedupe |
| “feedback dashboard” customer copy | Customer-facing success copy without ops tooling jargon |
| Signup caption named Supabase | Customer email-confirmation guidance |
| Privacy note said “MVP” | Founder Beta product wording |
| Notification Center could be mistaken for live push | Explicit “sample alerts” Founder Beta note |
| Stale Trade Hub “section filters” roadmap | Updated to unified ranked feed |

## Measured timings (logged-out AppTest / fixtures)

| Surface | Wall / server |
| --- | --- |
| Cold startup (server) | ~370 ms (budget 2,500) |
| Warm startup (server) | ~64 ms (budget 750) |
| Cold protobuf | 505,851 B (budget 510,000) |
| Warm protobuf | 463,397 B |
| Fixture Dashboard | ~116–119 ms |
| Fixture Trade Hub | ~98 ms |
| Fixture My Team | ~98 ms |
| Fixture Waivers | ~103–104 ms |
| Fixture League | ~98 ms |

Authenticated login/logout/league-switch/Trade Hub generation wall times require
production credentials and remain an Ops measurement gap (same as LC0 / #115).

### Slowest operations (logged-out)

1. Cold public-player load
2. Large HTML ForwardMsg / CSS protobuf
3. Authenticated Trade Hub board generation (historical; not re-run with credentials)
4. Valuation lens every rerun (unchanged by design)

No speculative performance changes in this PR — #115 already shipped measured plumbing wins.

## Production safety checks run

| Check | Result |
| --- | --- |
| Full pytest | green (see PR CI) |
| `deployment_check.py` | passed |
| `audit_context_integrity.py` | `valid: true` |
| `audit_experimental_features.py` | no missing/stale routes |
| Performance budget | passed |
| Chromium mobile UI (when UI paths touched) | required green |
| Banned developer phrases in customer surfaces | covered by `tests/test_founder_beta_launch_candidate.py` |

## Trade Hub launch contract

- Unified ranked recommendation feed (no category pills)
- Per-card category badges
- Review package → detail path unchanged
- Search / return paths retained
- `trade_hub_opened` analytics once per session

## Feedback

- Profile menu entry under You
- Submit → Supabase preferred path with JSONL fallback
- Success copy customer-facing
- `feedback_submitted` analytics when saved

## Analytics contract (all nine events wired)

`landing_visit`, `account_created`, `league_imported`, `dashboard_reached`,
`trade_hub_opened`, `player_quick_view_opened`, `premium_checkout_started`,
`premium_checkout_completed`, `feedback_submitted`

Deduped with `once_key` where spam risk exists. Enabled only when
`DYNASTYGM_LAUNCH_ANALYTICS=1`.

## Remaining launch blockers (Ops — not code)

### P0 — before charging money

| ID | Task |
| --- | --- |
| LC0-P0-1 | Apply `docs/supabase_entitlement_security_hardening.sql` in production |
| LC0-P0-2 | Apply `docs/supabase_feedback.sql` in production |
| LC0-P0-3 | Stripe test-mode lifecycle on production URLs |
| LC0-P0-4 | Render Streamlit has **no** `SUPABASE_SERVICE_ROLE_KEY` |
| LC0-P0-5 | Fresh Free + Premium production walkthrough |

### P1

| ID | Task |
| --- | --- |
| LC0-P1-1 | Live Stripe billing review (when intentionally enabling charges) |
| LC0-P1-2 | Confirm one production feedback row in Table Editor |
| LC0-P1-3 | Customer Portal cancel-at-period-end on production |
| LC0-P1-4 | External provider freshness vs live Sleeper evidence |

### Product notes (non-blocking)

- Notification Center remains Founder Beta sample alerts until live delivery
- Authenticated performance observation still needed on production
- Browser history quirks in fixture harness (FQA-005) are review-only

## Explicit non-changes

Football formulas, valuations, rankings, recommendation ordering, Trust
enforcement, Stripe charge/webhook entitlement mapping, Supabase schema,
authentication rules, and business rules were not modified except analytics
hooks and customer-facing copy.
