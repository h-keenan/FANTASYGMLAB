# Production Launch Configuration Inventory (#228)

Ops / configuration inventory for turning #227 **CONDITIONAL GO** into an operable launch gate.
**No secret values are recorded here.**

| Field | Value |
| --- | --- |
| Baseline (#227) | `880e8556cadedbfd294ee1bc29fecaa3f2cf880c` |
| Scope | Production configuration, domains, Stripe/Supabase Ops, flags, analytics, trust, hosting |
| Agent access | No Render API, Stripe dashboard, or Supabase Auth dashboard write access in this environment |
| Live topology probe (2026-08-09) | **NOT READY** — apex/www still Streamlit; `app.` returns Porkbun 404; webhook `/health` 404 |

Master checklist: [`production-launch-checklist.md`](production-launch-checklist.md)  
Smoke script: [`production-launch-smoke-test.md`](production-launch-smoke-test.md)  
Domain cutover detail: [`production-domain-cutover.md`](production-domain-cutover.md)

---

## Intended domain topology

| Host | Owner | Role |
| --- | --- | --- |
| `https://fantasygmlab.com` | **Not a separate Render marketing service today** | May be Streamlit, DNS, or future/external marketing — do not assume `fantasygm-lab-marketing` is deployed |
| `https://www.fantasygmlab.com` | Same as apex unless DNS says otherwise | Do not assume a static marketing service |
| `https://app.fantasygmlab.com` | Render web `FANTASYGMLAB` | Streamlit app — **canonical auth/billing origin** |
| Render default hostname | Render | Legacy/internal; do not market |
| `fantasygmlab-stripe-webhook` hostname | Render web `fantasygmlab-stripe-webhook` | Stripe webhook; mode must match checkout |

### Actual verifiable state (public probe, 2026-08-09)

| Probe | Result |
| --- | --- |
| Apex HTML | Streamlit (not static landing) |
| www HTML | Streamlit |
| `app.` | HTTP 404 (Porkbun parking / not attached) |
| `app./_stcore/health` | 404 |
| `fantasygmlab.onrender.com/_stcore/health` | 200 `ok` (~100–300 ms while awake) |
| Webhook `/health` | 404 (`x-render-routing: no-server` historically) |

**Cutover has not completed.** Do not treat marketing CTA `https://app.fantasygmlab.com` as live until DNS + Render domains match target topology.

### Supported vs legacy hosts (transition)

| Host | Auth/billing | Policy |
| --- | --- | --- |
| `app.fantasygmlab.com` | **Canonical** | Target Site URL + Stripe returns |
| Apex/www while still Streamlit | Legacy dual-host | Works only if Supabase allowlist still includes them; **do not** force brittle redirects in app code |
| `*.onrender.com` | Legacy | Keep reachable for Ops; remove from marketing |

---

## Stripe live billing flag

| Flag | Meaning |
| --- | --- |
| **STRIPE LIVE BILLING: OFF** | Missing/incomplete configuration or key/mode mismatch |
| **STRIPE LIVE BILLING: READY** | Test-mode secret + monthly/annual price ids configured; UI states “No live charge will be made.” |
| **STRIPE LIVE BILLING: ON** | Explicit `STRIPE_BILLING_MODE=live` with matching live secret and monthly/annual prices |

Helper: `modules.stripe_billing.stripe_live_billing_status()` → `OFF` | `READY` | `ON`.

**Display price:** App does not show a hard-coded dollar amount; Stripe Checkout owns the amount from price ids. Launch decision: do **not** invent an in-app price; confirm amount in Stripe Dashboard Test/Live Price before charging.

---

## Environment / secret inventory

Legend — **Fail behavior:** fail-open = product continues without feature; fail-closed = feature blocked / errors safely.

### Streamlit service `FANTASYGMLAB` (Render + Streamlit secrets)

| Name | Purpose | Req | Prod type | Secret | Missing default | Fail | Launch req | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `APP_BASE_URL` | Canonical app origin for Stripe returns / deep links | Yes (prod) | URL | No | Local → `http://localhost:8501`; **managed host → `https://app.fantasygmlab.com`** (#228) | Fail-closed to prod URL on Render | **YES** | Render / app config |
| `SUPABASE_URL` | Auth + profiles API | Yes | URL | No | empty → auth unavailable | Fail-closed auth | **YES** | Supabase / Render |
| `SUPABASE_ANON_KEY` | Client auth key | Yes | JWT | **Yes** | empty → auth unavailable | Fail-closed auth | **YES** | Supabase / Render |
| `SUPABASE_SERVICE_ROLE_KEY` | Must **not** be on Streamlit | No | JWT | **Yes** | n/a | — | Must be **absent** | Render |
| `STRIPE_BILLING_MODE` | Explicit Stripe environment | Yes if billing | `test` or `live` | No | `test` | Key/mode mismatch fails closed | **YES** | Stripe / Render |
| `STRIPE_SECRET_KEY` | Checkout / portal | For billing | matching `sk_test_…` or `sk_live_…` | **Yes** | empty → billing not configured | Fail-closed checkout | YES if charging | Stripe / Render |
| `STRIPE_PRICE_MONTHLY` | Monthly price id | For billing | `price_…` | No* | empty → not configured | Fail-closed | YES if charging | Stripe / Render |
| `STRIPE_PRICE_ANNUAL` | Annual price id | For billing | `price_…` | No* | empty → not configured | Fail-closed | YES if charging | Stripe / Render |
| `STRIPE_CHECKOUT_SUCCESS_URL` | Override success return | Recommended | URL | No | built from `APP_BASE_URL` + `/?page=premium&billing=success` | Safe default | YES shape on app host | Stripe / Render |
| `STRIPE_CHECKOUT_CANCEL_URL` | Override cancel return | Recommended | URL | No | `…&billing=cancel` | Safe default | YES shape on app host | Stripe / Render |
| `STRIPE_CUSTOMER_PORTAL_RETURN_URL` | Portal return | Recommended | URL | No | `/?page=premium` on app base | Safe default | YES if portal used | Stripe / Render |
| `STRIPE_WEBHOOK_SECRET` | Must **not** be needed on Streamlit | No | `whsec_…` | **Yes** | n/a | — | On webhook service only | Stripe / Render |
| `DYNASTYGM_BUILD` | Footer / deploy marker | Recommended | short SHA/label | No | empty → unmarked | Fail-open | YES for SHA verify | Render / app config |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | Master experimental nav | No | bool | No | **false** | Safe OFF | Must stay OFF | app config |
| `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | DM kill switch | No | bool | No | **ON** unless explicitly `0/false` | Graduated default ON | Kill only in incident | app config |
| `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | GM Targets kill switch | No | bool | No | **ON** unless explicitly `0/false` | Graduated default ON | Kill only in incident | app config |
| `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` | Share kill switch | No | bool | No | **ON** unless explicitly `0/false` | Graduated default ON | Kill only in incident | app config |
| `DYNASTYGM_LAUNCH_ANALYTICS` | JSONL analytics | Optional | bool | No | **false** (off) | Fail-open (no events) | Optional for launch; enable for funnel | app config |
| `DYNASTYGM_LAUNCH_ANALYTICS_PATH` | JSONL path override | Optional | path | No | `data/launch_analytics.jsonl` | Fail-open | No | app config |
| `DYNASTYGM_FOUNDER_OPS` | Founder ops dashboard | Optional | bool | No | false | Fail-closed UI | No | app config |
| `DYNASTYGM_ALLOW_PROD_DEBUG` | Unlock debug on managed host | **Never prod** | bool | No | false | Safe fail-closed | Must be unset | app config |
| `DYNASTYGM_DEBUG_PERF` | Performance Report UI | Dev only | bool | No | false; ignored on Render without allow | Safe | Must be unset | app config |
| `DYNASTYGM_DEBUG_AUTH` | Auth debug | Dev only | bool | No | false; managed-host locked | Safe | Must be unset | app config |
| `DYNASTYGM_PREMIUM_OVERRIDE` | Force Premium locally | Dev only | bool | No | false; managed-host locked | Safe | Must be unset | app config |
| `DYNASTYGM_SHOW_DEV_DESTINATIONS` | Dev nav | Dev only | bool | No | false; managed-host locked | Safe | Must be unset | app config |
| `DYNASTYGM_DEV_RELOAD_MODULES` | Hot reload | Dev only | bool | No | false | Safe | Must be unset | app config |
| `DYNASTYGM_WEBHOOK_HEALTH_URL` | Founder Ops probe | Optional | URL | No | no default; `not_configured` when absent | Fail-open | No | app config |
| `PYTHON_VERSION` | Runtime | Yes | `3.12.10` | No | Blueprint sets | — | YES | Render |
| `RENDER` / `RENDER_SERVICE_ID` / `RENDER_EXTERNAL_URL` | Managed-host detection | Platform | set by Render | No | unset locally | — | Auto | Render |

\*Price ids are not high-sensitivity but treat as config, not public marketing copy.

### Webhook service `fantasygmlab-stripe-webhook`

| Name | Purpose | Req | Secret | Missing | Fail | Launch req | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `STRIPE_SECRET_KEY` | Test mode API | Yes | **Yes** | 503/not ready | Fail-closed | **YES** for entitlement | Stripe / Render |
| `STRIPE_WEBHOOK_SECRET` | Signature verify | Yes | **Yes** | reject unsigned | Fail-closed | **YES** | Stripe / Render |
| `SUPABASE_URL` | Profile updates | Yes | No | not ready | Fail-closed | **YES** | Supabase / Render |
| `SUPABASE_SERVICE_ROLE_KEY` | Entitlement writes | Yes | **Yes** | not ready | Fail-closed | **YES** | Supabase / Render |

### Marketing static site

**Not currently deployed** as a Render service. Repo `static/landing/` and any
Blueprint name `fantasygm-lab-marketing` are future/external architecture only.
Do not create that service in this hygiene pass. No app secrets belong there if
it is ever deployed.

### Defaults classification

| Default | Class |
| --- | --- |
| Experiment flags unset → OFF | **SAFE PRODUCTION DEFAULT** |
| Analytics unset → OFF | **SAFE PRODUCTION DEFAULT** (enable intentionally) |
| Debug flags unset → OFF; managed host locked | **SAFE FAIL-CLOSED** |
| `APP_BASE_URL` unset locally → localhost | **DEVELOPMENT ONLY** |
| `APP_BASE_URL` unset on Render → `https://app.fantasygmlab.com` | **SAFE PRODUCTION DEFAULT** (#228) |
| Stripe without `sk_test_` → checkout unavailable | **SAFE FAIL-CLOSED** |
| Live Stripe key → rejected | **SAFE FAIL-CLOSED** |
| Missing Supabase anon → auth unavailable | **LAUNCH BLOCKER IF UNSET** |
| Webhook service missing | **LAUNCH BLOCKER IF UNSET** (if Premium checkout offered) |

---

## Supabase Auth (dashboard — MANUAL)

Project referenced in prior Ops docs: **DynastyGM** (`ejbwbnlelwvdyabyptqn`) — **not re-verified in #228**.

Required settings (founder must confirm in Supabase Dashboard → Authentication → URL configuration):

| Setting | Required value |
| --- | --- |
| Site URL | `https://app.fantasygmlab.com` |
| Redirect allowlist | `https://app.fantasygmlab.com`, `https://app.fantasygmlab.com/**` |
| Dev (optional) | `http://localhost:8501`, `http://localhost:8501/**` |
| Legacy overlap (temporary only) | Prior apex/www Streamlit URLs **only** until cutover completes, then remove |

Code note: signup/signin use Supabase client defaults; redirects are governed by dashboard Site URL / email templates. **MANUAL — FOUNDER ACTION REQUIRED** to confirm dashboard values.

### Email confirmation interruption

If confirmation is required: guest state must not be corrupted; after confirm, user returns via allowlisted URL and can resume league / Premium intent (#224 continuity). Manual smoke steps in smoke-test doc.

---

## Stripe webhook contract (code truth)

| Item | Value |
| --- | --- |
| Endpoint | `POST /stripe/webhook` on webhook service |
| Health | `GET /health` |
| Signature | Stripe-Signature + `STRIPE_WEBHOOK_SECRET` |
| Active → Premium | `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `invoice.payment_succeeded` |
| Inactive → Free | `customer.subscription.deleted`; also unpaid/canceled statuses; `invoice.payment_failed` → free |
| Authority | **Webhook + Supabase profile entitlement** is authoritative; browser return clears memo / analytics but must not sole-grant Premium |
| Failure modes | Bad/missing signature → 4xx; unknown event → no entitlement change; missing user metadata → no grant; Supabase failure → no silent Premium |

Portal: Manage Billing button only when `stripe_customer_id` present; errors show warning (no dead infinite spinner). Portal requires Stripe Customer Portal enabled in Dashboard (**MANUAL**).

---

## Feature flags / diagnostics (production launch state)

| Flag | Launch state |
| --- | --- |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | **OFF** |
| Decision Memory / GM Targets / Share | **ON** (kill with `DYNASTYGM_EXPERIMENTAL_*=0`); master `SHOW_EXPERIMENTAL` remains **OFF** |
| Live Draft | Conditional (active draft only; not experimental chip) |
| Player Explorer / Trade Analyzer / Weekly Report / Teams / Tendencies / ESPN | OFF / archived per #226 |
| `DYNASTYGM_DEBUG_*` / `ALLOW_PROD_DEBUG` | **OFF** |
| `DYNASTYGM_LAUNCH_ANALYTICS` | Optional ON for funnel; default OFF |

---

## Analytics

| Item | Behavior |
| --- | --- |
| Provider | Host-local JSONL (`modules/launch_analytics.py`) — not a third-party pixel |
| Enable | `DYNASTYGM_LAUNCH_ANALYTICS=1` |
| Fail | Write errors swallowed |
| PII | Email, fantasy username, tokens, raw Stripe ids, private notes blocked |
| Critical events | Guest username/league/first useful/signup*; Premium gate/CTA/checkout*/entitlement/portal |

---

## SEO / marketing / trust

| Surface | Status |
| --- | --- |
| Static title/description/canonical/OG/favicon | Present in `static/landing/index.html` |
| CTA | `https://app.fantasygmlab.com/?utm_source=static_landing&utm_medium=cta` |
| robots.txt | `Allow: /` + sitemap line to apex |
| App indexing | `noindex, nofollow` injected in `app.py` |
| Premium included list on static | Aligned to `PREMIUM_INCLUDED_NOW` (#228; removed experimental items) |
| In-app Terms / Privacy / About | Present via `modules/legal_pages.py` |
| Support email | **Not published** as a real address; `support@example.com` remains placeholder in setup docs — **MANUAL / LEGAL** if public support required |
| Cancellation language | “No live charge” / portal-based manage; no unsupported “instant cancel” legal promises |

---

## Render services

| Service (dashboard) | Type | Start / path | Health | Domain target | Always-on |
| --- | --- | --- | --- | --- | --- |
| `FANTASYGMLAB` | Python web | `streamlit run app.py …` | `/_stcore/health` | `app.fantasygmlab.com` (when attached) | **Required** paid always-on (Blueprint cannot set plan) |
| Marketing static | — | **Not currently deployed** | — | future/external only | — |
| `fantasygmlab-stripe-webhook` | Python web | uvicorn webhook | `/health` | Render hostname | Should stay awake for billing |

Deploy SHA: set `DYNASTYGM_BUILD` to short SHA; verify footer `BUILD … · MAIN`.

---

## GitHub Actions billing

Known external blocker. Do not weaken CI. Local equivalents: full pytest, compileall, `git diff --check`, performance budget, protobuf size. After billing restored: re-run Delivery Validation + browser/mobile workflows on launch SHA.

---

## Rollback levels

| Level | Trigger | Action | Recovery | Data risk | Owner |
| --- | --- | --- | --- | --- | --- |
| 1 Code | Bad deploy / P0 traceback | Redeploy known-good SHA (see checklist) | Previous build | Low if DB unchanged | Founder / Render |
| 2 Billing | Checkout/webhook incident | Unset Stripe secrets / disable checkout config; keep app up | Free product continues | Subscriptions may need Stripe Dashboard reconcile | Founder / Stripe |
| 3 Experiments | Unexpected experimental UI | Ensure all `DYNASTYGM_EXPERIMENTAL_*` and `SHOW_EXPERIMENTAL` unset | Experiments OFF | None | Founder / Render |
| 4 Domain | Wrong host serving app/marketing | Restore prior DNS/custom domains | Previous topology | Auth cookies origin-scoped | Founder / DNS / Render |

**Known-good rollback boundary (#227):** `880e8556cadedbfd294ee1bc29fecaa3f2cf880c`  
After #228 merges: record #228 merge SHA as primary launch candidate; keep #227 as rollback floor for this Ops package.
