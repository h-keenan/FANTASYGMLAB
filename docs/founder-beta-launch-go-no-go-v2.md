> HISTORICAL EVIDENCE: this report records past probes of a guessed hostname and past topology assumptions. It is no longer deployment or runbook authority. Do not execute its service-creation instructions. See [current webhook operations](webhook-operational-authority.md).

# Founder Beta Launch Go / No-Go Gate v2

Final paid Founder Beta intake gate. Re-runs unresolved **P0** items from
[`docs/founder-beta-launch-go-no-go.md`](founder-beta-launch-go-no-go.md) (PR #165)
against latest `main` after PR #168.

| Field | Value |
| --- | --- |
| Gate date (UTC) | 2026-08-07 |
| Prompt baseline (`main` after PR #168) | `06ef43fc5d41be872388eb978573a713a23d7a20` |
| Production footer evidence | `BUILD 06EF43F · MAIN` |
| Scope | Ops closure & verification only — no football logic, valuations, rankings, Trust, recommendation ordering, product redesign, or new experimental features |
| Agent credentials | No Render dashboard API; no Stripe secret values; Supabase MCP for schema/RLS/feedback probes; Chromium guest production smoke |

## Final launch verdict

**NO-GO — remaining P0 blockers: Stripe webhook `/health` still 404 on `fantasygm-lab-stripe-webhook.onrender.com`; Stripe Test Mode secrets/prices still not configured on Streamlit (Premium shows billing-disabled copy, no checkout CTA); Stripe Test Mode lifecycle (monthly/annual/failed payment/portal/cancel/webhook grant/replay/signature) not verified on production; Streamlit secret-boundary (no `SUPABASE_SERVICE_ROLE_KEY`) not founder-dashboard confirmed; fresh Free and fresh Premium authenticated walkthroughs not completed**

Do **not** accept paid Founder Beta customers until every FAIL/BLOCKED P0 gate below is green.

## Gate table

| Gate | Status | Evidence | Severity |
| --- | --- | --- | --- |
| production deploy | PASS | `www.fantasygmlab.com` HTTPS 200; `/_stcore/health` → `ok` (~87ms awake); apex → www; Render host 200; footer **`BUILD 06EF43F · MAIN`** matches baseline `06ef43f`; no Founder Ops / Performance Report for guest | P0 |
| Supabase migrations | PASS | Tables present with expected columns: `profiles` (+ `stripe_*`, `entitlement`), `saved_leagues`, `user_settings`, `feedback_reports`, `decision_memory_*`, `gm_targets`. Trigger `profiles_enforce_entitlement_authority` present. | P0 |
| RLS | PASS | RLS enabled on all public app tables. Own-row policies for authenticated users. Feedback guest insert + select-own. Decision Memory / GM Targets own-row only. | P0 |
| Streamlit secret boundary | BLOCKED | Repo `render.yaml` contract: Streamlit has **no** `SUPABASE_SERVICE_ROLE_KEY`; webhook service does. Live Render Streamlit env name inventory **not** founder-confirmed this gate. | P0 |
| Stripe monthly | FAIL | Guest Premium: “Premium checkout will appear here once billing is enabled… Live billing is not enabled.” No “Start Founder Premium checkout”; no monthly CTA. | P0 |
| Stripe annual | FAIL | Same — annual checkout not available without Test Mode price/config. | P0 |
| failed payment | BLOCKED | Cannot run without checkout. | P0 |
| portal | BLOCKED | Cannot run without Premium via webhook. | P0 |
| cancellation | BLOCKED | Cancel-at-period-end / active-until-end / downgrade not run on production. | P0 |
| webhook health | FAIL | `GET https://fantasygm-lab-stripe-webhook.onrender.com/health` → **HTTP 404**. `GET/POST …/stripe/webhook` → **404**. Treat as undeployed or wrong public hostname. | P0 |
| fresh Free walkthrough | BLOCKED | Guest path smoke PASS. Fresh signed-in Free account (signup/import/full surface) **not run** (email/auth required; founder/dev excluded). | P0 |
| fresh Premium walkthrough | BLOCKED | Blocked on Stripe Test Mode + webhook. | P0 |
| feedback | PASS | Prior durable guest row still present: `feedback_reports.report_id=a05ec5fe-2cd4-41df-b7af-719e14501f1a`, `user_id` null, `app_build=10e384f`. Schema/RLS unchanged. Authenticated Free/Premium submit not re-run (auth required). | P0 |
| analytics | PASS-WITH-LIMIT | Kill switch `DYNASTYGM_LAUNCH_ANALYTICS` (default off). Host-local JSONL persistence limitation unchanged. Not a product breaker when unset. | P1 |
| experimental flags | PASS | Guest: ESPN labeled “ESPN experimental”; no unlabeled Decision Memory / GM Targets destinations; no Performance Report; no Founder Ops. Decision Memory / GM Targets remain **flag-off** → non-blocking for paid intake (document only). | P0 |
| Founder Ops | BLOCKED | Guest isolation PASS (not visible). Authenticated founder card review (build/env/analytics/feedback/webhook/Supabase) **not run**. | P1 |
| performance smoke | PASS-PARTIAL | Awake `/_stcore/health` ~87ms; Premium + Dashboard guest shells usable. No broad rewrite. Full warm interaction budgets remain local AppTest territory (#166). No permanent blank/crash on awake probe. | P1 |
| UI smoke | PASS-PARTIAL | Guest 390: command bar (Select League / Alerts / You / GM) present; Alerts opens without “Inbox” noun; Premium Free badge; experimental ESPN labeled; footer build correct; no debug UI. Authenticated flows deferred. | P1 |
| security | PASS-PARTIAL | RLS + entitlement trigger confirmed; webhook signature code present in repo; service-role intended webhook-only in `render.yaml`. **Not** verified live: Streamlit env inventory; webhook signature rejection on deployed host; live-mode key rejection. Advisors: WARN `set_updated_at` / entitlement function search_path; leaked-password protection disabled (P1). | P0 / P1 |

## Production deploy evidence

| Check | Result |
| --- | --- |
| Probed at (UTC) | 2026-08-07T17:32:34Z (`scripts/founder_beta_ops_public_probe.py`) + Chromium ~17:35Z |
| `https://fantasygmlab.com/` | 200 → `https://www.fantasygmlab.com/` |
| `https://www.fantasygmlab.com/` | 200 |
| `/_stcore/health` | 200 `ok` |
| `https://fantasygmlab.onrender.com/` | 200 |
| Footer SHA | `BUILD 06EF43F · MAIN` (matches post-#168 `06ef43f`) |
| Debug / Performance Report | Not present (guest) |
| Founder Ops (guest) | Not present |
| Stale deploy | No — matches latest intended main |

## Streamlit secret-boundary checklist (names only)

**Hard requirement:** Streamlit must **not** contain `SUPABASE_SERVICE_ROLE_KEY`.

| Variable name | Intended Streamlit | Intended webhook | Notes |
| --- | --- | --- | --- |
| `SUPABASE_URL` | yes | yes | public project URL |
| `SUPABASE_ANON_KEY` | yes | no | anon/publishable |
| `SUPABASE_SERVICE_ROLE_KEY` | **NO** | yes | webhook only — P0 if on Streamlit |
| `STRIPE_SECRET_KEY` | yes (`sk_test_…` only) | yes (`sk_test_…`) | never live for this gate |
| `STRIPE_PRICE_MONTHLY` | yes | — | test price id |
| `STRIPE_PRICE_ANNUAL` | yes | — | test price id |
| `STRIPE_CHECKOUT_SUCCESS_URL` | yes | — | production return |
| `STRIPE_CHECKOUT_CANCEL_URL` | yes | — | production cancel |
| `STRIPE_CUSTOMER_PORTAL_RETURN_URL` | yes | — | portal return |
| `STRIPE_WEBHOOK_SECRET` | no | yes | signing secret |
| `APP_BASE_URL` | yes | — | `https://fantasygmlab.com` |
| `DYNASTYGM_BUILD` | optional | — | footer may use `RENDER_GIT_COMMIT` |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | unset/false | — | destinations |
| `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | unset/false unless intentional | — | kill switch |
| `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | unset/false unless intentional | — | kill switch |
| `DYNASTYGM_LAUNCH_ANALYTICS` | optional | — | host-local JSONL |
| `DYNASTYGM_FOUNDER_OPS` | founder only | — | Founder Ops gate |
| `DYNASTYGM_DEBUG_PERF` | **unset** | — | Performance Report |
| `DYNASTYGM_DEBUG_AUTH` | **unset** | — | auth debug |
| `DYNASTYGM_PREMIUM_OVERRIDE` | **unset** | — | entitlement override |
| `DYNASTYGM_SHOW_DEV_DESTINATIONS` | **unset** | — | dev routes |
| `DYNASTYGM_ALLOW_PROD_DEBUG` | **unset** | — | managed-host escape |
| `DYNASTYGM_WEBHOOK_HEALTH_URL` | optional Founder Ops | — | health probe URL |

**Status:** Code/`render.yaml` contract PASS. Live Render env name inventory **BLOCKED** (no Render API). Founder must screenshot Streamlit env list proving **no** `SUPABASE_SERVICE_ROLE_KEY`.

## Webhook service

| Check | Result |
| --- | --- |
| Dedicated service in `render.yaml` | `fantasygm-lab-stripe-webhook`, `uvicorn …stripe_webhook_service`, `healthCheckPath: /health` |
| Code `/health` | Returns `{"status":"ok","service":"stripe-webhook"}` |
| Public `GET …/health` | **404** (P0) |
| Public `POST …/stripe/webhook` | **404** (P0) |
| Service-role only on webhook | Contract PASS; live env unconfirmed |
| Verdict rule | If `/health` still fails → **NO-GO** (met) |

## Stripe Test Mode lifecycle

| Scenario | Result |
| --- | --- |
| Monthly Free→Premium | **Not run** — billing not configured |
| Annual | **Not run** |
| Failed payment card | **Not run** |
| Webhook entitlement grant | **Not run** — host 404 |
| Customer Portal | **Not run** |
| Cancel at period end / active-until-end / downgrade | **Not run** |
| past_due / unpaid / replay / bad signature / live-mode reject | **Not run** on production host |
| Live Stripe keys | Correctly **not** enabled (Premium copy: live billing not enabled) |

Local automated Stripe contracts remain green in repo; they do **not** replace production Test Mode proof.

## Fresh account walkthroughs

| Persona | Result |
| --- | --- |
| Guest | PASS — launch, Premium Free plan, Alerts (no Inbox), GM present, ESPN experimental labeled, no founder/debug UI, build `06EF43F` |
| Fresh Free (non-founder) | **Not run** |
| Fresh Premium via Stripe test | **Not run** |

## Decision Memory / GM Targets

| Feature | Flag | Production status | Launch impact |
| --- | --- | --- | --- |
| Decision Memory | `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | Migrations applied; feature remains **off** / not customer-activated | Non-blocking |
| GM Targets | `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | Migrations applied; feature remains **off** / not customer-activated | Non-blocking |

Do **not** enable either for paid intake without a separate activation pass.

## Analytics

- Kill switch: `DYNASTYGM_LAUNCH_ANALYTICS=1`
- Persistence: host-local JSONL (Render ephemeral) — honest limitation
- Failure mode: does not break customer flows when unset → not automatic P0

## Security sanity

| Check | Status |
| --- | --- |
| RLS on required tables | PASS |
| Entitlement cannot self-grant (DB trigger) | PASS |
| Service-role isolation (contract) | PASS in repo; Render confirmation BLOCKED |
| Stripe webhook signature (code) | PASS in repo; live host FAIL (404) |
| Account / league isolation (RLS own-row) | PASS schema |
| No customer stack traces / debug UI (guest) | PASS |
| Advisors | WARN search_path + leaked-password protection disabled (P1) |

## Remaining blockers

### P0 (must clear before paid intake)

1. Deploy reachable Stripe webhook service; `GET /health` → success JSON; document real hostname; prove `POST /stripe/webhook` reachable (signature failures ≠ 404).
2. Configure Streamlit **test** Stripe secrets + monthly/annual price ids + return URLs; prove checkout CTAs appear.
3. Confirm Streamlit env has **no** `SUPABASE_SERVICE_ROLE_KEY`; unset debug/override flags; webhook env has service-role + test webhook secret + test Stripe secret.
4. Complete Stripe Test Mode lifecycle on production URLs (monthly, annual, failed payment, portal, cancel-at-period-end, webhook grant, replay, bad signature, live-mode reject).
5. Fresh Free authenticated walkthrough (non-founder).
6. Fresh Premium authenticated walkthrough after test checkout (non-founder).

### P1

1. Founder Ops authenticated card review with live webhook health URL.
2. Production analytics enablement decision (accept host-local JSONL or durable store later).
3. Enable Supabase Auth leaked-password protection; fix mutable `search_path` on trigger helpers.
4. Authenticated UI/performance smoke on live leagues (beyond guest).

## Manual actions still required (founder)

1. Render: create/fix/deploy `fantasygm-lab-stripe-webhook` (or document true public URL); set webhook env (`STRIPE_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, test `STRIPE_SECRET_KEY`).
2. Render Streamlit: set test Stripe keys/prices/URLs; confirm secret-boundary inventory; unset debug flags.
3. Stripe Dashboard (Test Mode): endpoint → production webhook URL; required events per `docs/STRIPE_TEST_MODE_SETUP.md`.
4. Run fresh Free + Premium walkthroughs; record evidence.
5. Re-run this v2 gate → upgrade verdict to **GO FOR PAID FOUNDER BETA** only when all P0 rows are PASS.

## What changed vs PR #165

| Item | #165 | This v2 gate |
| --- | --- | --- |
| Production build | `10E384F` | `06EF43F` (post #166/#167/#168) |
| Supabase SQL/RLS | Applied + PASS | Still PASS (re-probed) |
| Feedback durability | Proven | Prior row still present |
| Webhook `/health` | 404 | **Still 404** |
| Stripe Test Mode on Streamlit | Not configured | **Still not configured** |
| Authenticated Free/Premium | Not run | **Still not run** |
| Secret-boundary live confirm | Not confirmed | **Still not confirmed** |
| Verdict | NO-GO | **NO-GO** (same P0 class) |

No product code changes were required or made to “fix” undeployed webhook / missing Stripe secrets — those are infrastructure Ops actions.

## Rollback boundary

- Product/code rollback: revert the merge commit for this PR on `main` (docs/probe/tests only).
- No new Supabase DDL in this gate.
- No football / valuation / ranking / Trust / recommendation-order changes.

## Related docs

- [`docs/founder-beta-launch-go-no-go.md`](founder-beta-launch-go-no-go.md) (v1 / PR #165)
- [`docs/founder-beta-ops-activation.md`](founder-beta-ops-activation.md)
- [`docs/STRIPE_TEST_MODE_SETUP.md`](STRIPE_TEST_MODE_SETUP.md)
- [`docs/RENDER_DEPLOYMENT.md`](RENDER_DEPLOYMENT.md)
