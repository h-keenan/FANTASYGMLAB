# Founder Beta Launch Go / No-Go Gate

Binary launch decision for paid Founder Beta intake on production.

| Field | Value |
| --- | --- |
| Gate date (UTC) | 2026-08-07 |
| Prompt baseline (`main` after PR #164) | `10e384fec0409949f2da413e2a2f55cb9d86d020` |
| Production footer evidence | `BUILD 10E384F • MAIN` |
| Scope | Ops closure & verification only — no football logic, valuations, rankings, Trust, recommendation ordering, product redesign, or new experimental features |
| Agent credentials | No Render dashboard API; no Stripe secret values; Supabase MCP used for schema probes + required SQL apply |

## Final launch verdict

**NO-GO — remaining P0 blockers: Stripe webhook `/health` 404; Stripe Test Mode secrets/prices not configured on Streamlit; Stripe Test Mode lifecycle (monthly/annual/portal/cancel/webhook) not verified on production URLs; Streamlit secret-boundary (no `SUPABASE_SERVICE_ROLE_KEY`) not founder-dashboard confirmed; fresh Free and fresh Premium authenticated walkthroughs not completed**

Do **not** accept paid Founder Beta customers until every FAIL/BLOCKED P0 gate below is green.

## Gate table

| Gate | Status | Evidence | Severity |
| --- | --- | --- | --- |
| production deployment | PASS | `www.fantasygmlab.com` HTTPS 200; `/_stcore/health` → `ok`; apex → www; Render host 200; footer `BUILD 10E384F • MAIN` matches baseline `10e384f` | P0 |
| Supabase migrations | PASS | Applied 2026-08-07 via Supabase MCP: `stripe_billing_profile_columns`, `entitlement_security_hardening`, `feedback_reports`, `decision_memory`, `gm_targets`. Tables present: `profiles`, `saved_leagues`, `user_settings`, `feedback_reports`, `decision_memory_events`, `decision_memory_baselines`, `gm_targets`. Stripe columns on `profiles`. | P0 |
| RLS | PASS | RLS enabled on all public app tables. Own-row policies for authenticated users. Decision Memory / GM Targets: no anon policies. Feedback: anon insert only with `user_id is null`; select own only. Entitlement trigger `profiles_enforce_entitlement_authority` present. | P0 |
| Stripe | FAIL | Guest Premium page: “checkout will appear here once billing is enabled”; no “Start Founder Premium checkout” control. Test Mode secrets/prices not configured on production Streamlit. Live keys not enabled (correct). | P0 |
| webhook | FAIL | `https://fantasygm-lab-stripe-webhook.onrender.com/health` → **HTTP 404**. Treat as undeployed or wrong hostname. `/stripe/webhook` not proven reachable. | P0 |
| Free account | BLOCKED | Guest path smoke PASS. Fresh signed-in Free account signup/import/full surface walkthrough **not run** (email/auth required; founder/dev account excluded). | P0 |
| Premium account | BLOCKED | Cannot run without Stripe Test Mode checkout + webhook. | P0 |
| entitlement persistence | BLOCKED | Hardening trigger applied in production DB. End-to-end Premium persist after webhook/refresh/logout **not proven** on production. | P0 |
| cancellation | BLOCKED | Customer Portal / cancel-at-period-end / active-until-end / eventual downgrade **not run** on production. | P0 |
| feedback | PASS | Production guest submit → durable row `feedback_reports.report_id=a05ec5fe-2cd4-41df-b7af-719e14501f1a`, `user_id` null (guest), `app_build=10e384f`, category Bug, message prefix matches probe text. JSONL not relied upon. | P0 |
| analytics | PASS-WITH-LIMIT | Code kill switch `DYNASTYGM_LAUNCH_ANALYTICS` (default off). Persistence is **host-local JSONL**, not Supabase. Production emission not required for launch; does not break user flows when unset. | P1 |
| experimental flags | PASS | Guest: ESPN import labeled “ESPN experimental”; Decision Memory / GM Targets labeled Experimental on Premium inventory; no unlabeled experimental destinations in guest nav; no Performance Report / Founder Ops for guest. Matrix below. | P0 |
| Founder Ops | BLOCKED | Guest cannot see Founder Ops (PASS isolation). Authenticated founder verification of live cards (build/env/analytics/feedback/webhook/Supabase) **not run** without founder login. | P1 |
| security | PASS-PARTIAL | RLS + entitlement trigger applied; service-role intended webhook-only in `render.yaml`; webhook signature code present in repo. **Not** verified: Streamlit env inventory on Render; live webhook signature rejection; live-mode rejection on deployed host. | P0 / P1 |
| production performance smoke | PASS-PARTIAL | Awake guest shell usable; Premium page loads. Full warm Dashboard/Trade Hub/PQV/league-switch timing deferred to PR #166. No obvious permanent blank/crash. | P1 |
| UI smoke | PASS-PARTIAL | Guest 1440 desktop: no debug UI, command chrome present, Alerts/GM/You usable, ESPN labeled. Mobile 390 + deeper UX deferred to PR #167. | P1 |

## Production deploy evidence

| Check | Result |
| --- | --- |
| Probed at (UTC) | 2026-08-07T16:32:33Z (`scripts/founder_beta_ops_public_probe.py`) |
| `https://fantasygmlab.com/` | 200 → `https://www.fantasygmlab.com/` |
| `https://www.fantasygmlab.com/` | 200 |
| `/_stcore/health` | 200 `ok` |
| `https://fantasygmlab.onrender.com/` | 200 |
| Footer SHA | `BUILD 10E384F • MAIN` (Chromium) |
| Debug / Performance Report UI | Not present for guest |
| Founder Ops UI (guest) | Not present |
| Stale deploy | No — matches post-#164 main |

Probe script: `python scripts/founder_beta_ops_public_probe.py`

## Supabase production verification checklist

Project: **DynastyGM** (`ejbwbnlelwvdyabyptqn`, us-west-2, ACTIVE_HEALTHY).

### Applied migrations (this gate)

1. `stripe_billing_profile_columns` — from `docs/supabase_stripe_billing.sql`
2. `entitlement_security_hardening` — from `docs/supabase_entitlement_security_hardening.sql`
3. `feedback_reports` — from `docs/supabase_feedback.sql`
4. `decision_memory` — from `docs/supabase_decision_memory.sql`
5. `gm_targets` — from `docs/supabase_gm_targets.sql`

### SQL probes (re-run anytime)

```sql
-- Tables
select table_name from information_schema.tables
where table_schema = 'public' order by 1;

-- RLS
select c.relname, c.relrowsecurity
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r' order by 1;

-- Entitlement authority
select tgname from pg_trigger
where tgrelid = 'public.profiles'::regclass and not tgisinternal;

-- Policies
select tablename, policyname, roles::text, cmd
from pg_policies where schemaname = 'public'
order by 1, 2;

-- Feedback durability
select report_id, created_at, user_id is null as guest, app_build, left(message, 80)
from public.feedback_reports order by created_at desc limit 5;
```

### Expected results after this gate

| Object | Expected |
| --- | --- |
| `feedback_reports` | exists, RLS on, select own + insert own + guest insert null uid |
| `decision_memory_*` | exists, RLS on, authenticated own-row only |
| `gm_targets` | exists, RLS on, authenticated own-row only (no update policy) |
| `profiles.entitlement` | free/premium check; client cannot change via trigger |
| `profiles.stripe_*` | columns present for webhook reconciliation |
| Account delete | profiles/saved_leagues/user_settings/decision_memory/gm_targets cascade with `auth.users`; feedback `user_id` set null |

## Streamlit secret-boundary inventory (names only)

**Hard requirement:** Streamlit must **not** contain `SUPABASE_SERVICE_ROLE_KEY`.

| Variable name | Intended Streamlit | Intended webhook service | Notes |
| --- | --- | --- | --- |
| `SUPABASE_URL` | yes | yes | public project URL |
| `SUPABASE_ANON_KEY` | yes | no | public anon/publishable |
| `SUPABASE_SERVICE_ROLE_KEY` | **NO** | yes | webhook only |
| `STRIPE_SECRET_KEY` | yes (test `sk_test_…`) | yes (test) | never live for this gate |
| `STRIPE_PRICE_MONTHLY` | yes | — | test price id |
| `STRIPE_PRICE_ANNUAL` | yes | — | test price id |
| `STRIPE_CHECKOUT_SUCCESS_URL` | yes | — | production return URL |
| `STRIPE_CHECKOUT_CANCEL_URL` | yes | — | production return URL |
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
| `DYNASTYGM_ALLOW_PROD_DEBUG` | **unset** | — | managed-host escape hatch |
| `DYNASTYGM_WEBHOOK_HEALTH_URL` | optional Founder Ops | — | health probe URL |

**Status:** Code/`render.yaml` contract PASS. Live Render env name inventory **not confirmed** in this environment (no Render API). Founder must screenshot Streamlit env list proving **no** `SUPABASE_SERVICE_ROLE_KEY`.

## Stripe Test Mode lifecycle

| Scenario | Result |
| --- | --- |
| Monthly Free→Premium checkout | **Not run** — billing not configured |
| Annual checkout | **Not run** |
| Webhook entitlement grant | **Not run** — webhook host 404 |
| Duplicate / idempotency | **Not run** (covered by unit tests only) |
| Failed payment | **Not run** |
| Customer Portal | **Not run** |
| Cancel at period end / active-until-end | **Not run** |
| Eventual downgrade | **Not run** |
| past_due / replay / bad signature / live-mode reject | **Not run** on production host |
| Live Stripe keys | Correctly **not** enabled |

Local automated Stripe contracts remain green in repo; they do **not** replace production Test Mode proof.

## Webhook service

| Check | Result |
| --- | --- |
| Dedicated service in `render.yaml` | `fantasygm-lab-stripe-webhook` with `/health` |
| Guessed public `/health` | **404** (P0) |
| `/stripe/webhook` | Not proven |
| Service-role only on webhook | Contract in yaml/docs; live env unconfirmed |
| Failure visibility in Founder Ops | Blocked on deploy + founder login |

## Fresh account walkthroughs

| Persona | Result |
| --- | --- |
| Guest | PASS — onboarding, Premium Free badge, labeled ESPN experimental, no Premium leakage chrome, no founder tools |
| Fresh Free (non-founder) | **Not run** |
| Fresh Premium via Stripe test | **Not run** |

## Experimental flag matrix

| Feature | Flag | Default | Production evidence (guest) | Free / Premium | Customer label |
| --- | --- | --- | --- | --- | --- |
| Decision Memory | `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | off | Listed on Premium inventory as Experimental; not a Free tool | Premium + flag | Experimental |
| GM Targets | `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | off | Listed on Premium inventory as Experimental; destination experimental | Premium + flag | Experimental |
| Live Draft | `DYNASTYGM_SHOW_EXPERIMENTAL` (destination) | off | Not in guest nav | Experimental destinations | Experimental |
| ESPN import | platform radio | available | “ESPN experimental” labeled | Guest/Free/Premium | experimental |
| Other EXPERIMENTAL destinations | `DYNASTYGM_SHOW_EXPERIMENTAL` | off | Locked on managed hosts without allow | — | Experimental when shown |
| Performance Report | `DYNASTYGM_DEBUG_PERF` | off | Not visible (guest) | debug | — |
| Founder Ops | `DYNASTYGM_FOUNDER_OPS` / founder gate | off for customers | Not visible (guest) | founder only | — |

No unlabeled experimental feature observed on guest production chrome.

## Analytics

- Kill switch: `DYNASTYGM_LAUNCH_ANALYTICS=1`
- Persistence: **host-local JSONL** (Render ephemeral FS) — honest limitation; not durable across redeploys
- Dedupe / retention / Founder Ops funnel: implemented in code (PR #164)
- Production event proof: not required for this GO if unset; not a P0 unless it breaks flows

## Security sanity

| Check | Status |
| --- | --- |
| RLS on required tables | PASS |
| Entitlement cannot self-grant (DB trigger) | PASS (applied this gate) |
| Service-role isolation (contract) | PASS in repo; Render confirmation BLOCKED |
| Stripe webhook signature (code) | PASS in repo; live host FAIL (404) |
| Account / league isolation (RLS own-row) | PASS schema |
| No secrets in frontend | PASS guest DOM probe |
| No customer stack traces | PASS guest smoke |
| Advisors | WARN only: `set_updated_at` search_path; leaked-password protection disabled (P1) |

## Production performance / UI notes (for later PRs)

| Item | Bucket |
| --- | --- |
| Full warm interaction budget (Dashboard / Trade Hub / PQV / league switch) | PR #166 |
| Mobile 390 polish, clipping, overlays, hierarchy | PR #167 |
| Support email / OG assets | marketing backlog |
| Auth leaked-password protection | post-launch / security hygiene |

## Remaining blockers

### P0 (must clear before paid intake)

1. Deploy reachable Stripe webhook service; `/health` → `{"status":"ok"}`; document real hostname.
2. Configure Streamlit **test** Stripe secrets + monthly/annual price ids + return URLs; prove checkout UI appears.
3. Confirm Streamlit env has **no** `SUPABASE_SERVICE_ROLE_KEY`; unset debug/override flags.
4. Complete Stripe Test Mode lifecycle on production URLs (monthly, annual, portal, cancel-at-period-end, webhook grant, replay, bad signature, live-mode reject).
5. Fresh Free authenticated walkthrough (non-founder).
6. Fresh Premium authenticated walkthrough after test checkout (non-founder).

### P1

1. Founder Ops authenticated card review with live webhook health URL.
2. Production analytics enablement decision (accept host-local JSONL limit or add durable store later).
3. Performance audit PR #166 / UI audit PR #167.
4. Enable Supabase Auth leaked-password protection; fix `set_updated_at` search_path.

## Manual actions still required (founder)

1. Render: deploy/fix webhook service URL; set webhook env (`STRIPE_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, test `STRIPE_SECRET_KEY`).
2. Render Streamlit: set test Stripe keys/prices/URLs; confirm secret-boundary inventory; unset debug flags.
3. Stripe Dashboard: Test Mode endpoint → production webhook URL; required events per `docs/STRIPE_TEST_MODE_SETUP.md`.
4. Run fresh Free + Premium walkthroughs; record evidence.
5. Re-run this gate doc statuses → upgrade verdict only when all P0 rows are PASS.

## Rollback boundary

- Product/code rollback: revert the merge commit for this PR on `main` (Render auto-deploy).
- Supabase SQL applied this gate is **additive** (tables/columns/trigger/policies). Do **not** drop tables to roll back; entitlement trigger removal would re-open self-grant and must not be done casually.
- No football / valuation / ranking / Trust / recommendation-order changes in this PR.

## Related docs

- [`docs/founder-beta-ops-activation.md`](founder-beta-ops-activation.md)
- [`docs/founder-beta-launch-verification.md`](founder-beta-launch-verification.md)
- [`docs/STRIPE_TEST_MODE_SETUP.md`](STRIPE_TEST_MODE_SETUP.md)
- [`docs/founder-beta-product-analytics-contract.md`](founder-beta-product-analytics-contract.md)
