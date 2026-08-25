# Runtime environment contract

Canonical inventory of values the **code** reads. **Secret values are never
recorded.** A founder dashboard inspection (2026-08-25) confirmed **two**
deployed Render services and presence/absence of key *names* only.

Authority order (intentional): **environment variable → Streamlit secrets →
`local_secrets/secrets.toml` → empty/default**. Do not guess from Render.

## Deployed Render topology (current)

| Dashboard name | Role |
| --- | --- |
| `FANTASYGMLAB` | Customer-facing Streamlit app |
| `fantasygmlab-stripe-webhook` | Stripe webhook / backend |

There is **no** separately deployed marketing Render service. `render.yaml` may
still list a static Blueprint entry (`fantasygm-lab-marketing`) as **future /
not currently deployed** architecture — do not treat it as live.

## Production vs local

| Mode | How detected | Missing required config |
| --- | --- | --- |
| Local / CI | `RENDER` / `RENDER_SERVICE_ID` / `RENDER_EXTERNAL_URL` unset | App may run without auth/billing; features fail closed |
| Managed web (`FANTASYGMLAB`) | Render injects those platform vars | Missing Supabase URL/anon, loopback `APP_BASE_URL`, or webhook-only secrets on the web process → `ProductionConfigurationError` (no guest/dev disguise) |
| Webhook (`fantasygmlab-stripe-webhook`) | Separate service | `/ready` returns 503; `/health` stays up. No startup provider calls |

Stripe checkout remains optional on the web process: missing prices/secret
disables checkout (fail-closed) and does **not** take down the app.

## Streamlit web — variables

| Name | Owner | Consumer(s) | Secret? | Prod required? | Dev required? | Default / fallback | Missing behavior | Still used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `APP_BASE_URL` | Render / local | `app_config`, Stripe returns, auth redirects | No | Yes (explicit recommended) | No | Managed: `https://app.fantasygmlab.com`; local: `http://localhost:8501` | Loopback on managed host fails closed | Yes |
| `SUPABASE_URL` | Supabase / Render | `auth_supabase`, webhook | No | **Yes** on managed web | No (auth off) | empty | Managed web fails closed; local auth unavailable | Yes |
| `SUPABASE_ANON_KEY` | Supabase / Render | `auth_supabase` | Yes (public client key, treat as credential) | **Yes** on managed web | No | empty | Same as URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase / Render | webhook only | **Yes** | Webhook yes; **must be absent** on Streamlit | No | empty | Forbidden on managed web (fail closed); webhook `/ready` 503 | Yes (webhook) |
| `STRIPE_SECRET_KEY` | Stripe / Render | `stripe_billing`, webhook | **Yes** | If charging | No | empty | Checkout unavailable | Yes |
| `STRIPE_BILLING_MODE` | Render | `stripe_billing` | No | If charging (`test` or `live`) | No | `test` | Live keys without `live` stay OFF | Yes |
| `STRIPE_PRICE_MONTHLY` | Stripe / Render | `stripe_billing` | No | If charging | No | empty | Checkout unavailable | Yes |
| `STRIPE_PRICE_ANNUAL` | Stripe / Render | `stripe_billing` | No | If charging | No | empty | Checkout unavailable | Yes |
| `STRIPE_CHECKOUT_SUCCESS_URL` | Render | `stripe_billing` | No | Recommended | No | built from `APP_BASE_URL` | Safe default | Yes |
| `STRIPE_CHECKOUT_CANCEL_URL` | Render | `stripe_billing` | No | Recommended | No | built from `APP_BASE_URL` | Safe default | Yes |
| `STRIPE_CUSTOMER_PORTAL_RETURN_URL` | Render | `stripe_billing` | No | If portal used | No | `/?page=premium` on app base | Safe default | Yes |
| `STRIPE_WEBHOOK_SECRET` | Stripe / Render | webhook only | **Yes** | Webhook yes; **must be absent** on Streamlit | No | empty | Forbidden on managed web; webhook unsigned events rejected | Yes (webhook) |
| `DYNASTYGM_BUILD` | Render optional | `build_identity` fallback | No | No (Render Git SHA preferred) | No | `local` | Unmarked local build | Yes |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | Render / local | destination visibility | No | Must stay unset/false | No | false; **forced false** on managed host without `DYNASTYGM_ALLOW_PROD_DEBUG` | Hidden experimental nav | Yes |
| `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | Render / local | kill switch | No | No | No | **ON** unless `0/false` | Graduated feature | Yes |
| `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | Render / local | kill switch | No | No | No | **ON** unless `0/false` | Graduated feature | Yes |
| `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` | Render / local | kill switch | No | No | No | **ON** unless `0/false` | Graduated feature | Yes |
| `DYNASTYGM_LAUNCH_ANALYTICS` | Render / local | `launch_analytics` | No | No | No | false | No events | Yes |
| `DYNASTYGM_LAUNCH_ANALYTICS_PATH` | local/ops | `launch_analytics` | No | No | No | `data/launch_analytics.jsonl` | Default path | Yes |
| `DYNASTYGM_ANALYTICS_ENV` | local/ops | `launch_analytics` | No | No | No | auto production/development/test | Stamp only | Yes |
| `DYNASTYGM_FOUNDER_OPS` | Render / local | Founder Ops dest | No | No | No | false | Hidden unless flag **and** `auth_user.app_metadata.founder_ops is True` | Yes |
| `DYNASTYGM_DEV_REVIEW` | Render / local | Founder Labs dest | No | No | No | false | Hidden unless flag **and** live session **and** (`founder_ops` or `dev_review` app_metadata) | Yes |
| `DYNASTYGM_WEBHOOK_HEALTH_URL` | Render / local | Founder Ops probe | No | No | No | default webhook `/health` | Fail-open probe | Yes |
| `DYNASTYGM_ALLOW_PROD_DEBUG` | never on customer Render | debug lock | No | Must be unset | No | false | Debug/override flags ignored on managed hosts | Yes (escape hatch) |
| `DYNASTYGM_PREMIUM_OVERRIDE` | local only | `premium` | No | Must be unset | No | false; managed-host locked | No fake Premium | Yes |
| `DYNASTYGM_DEBUG_AUTH` | local only | premium diagnostics | No | Must be unset | No | false; managed-host locked | Hidden | Yes |
| `DYNASTYGM_DEBUG_PERF` | local only | performance panel | No | Must be unset | No | false; managed-host locked | Hidden | Yes |
| `DYNASTYGM_DEBUG_UI` | local only | workspace / PQV debug | No | Must be unset | No | false | Hidden | Yes |
| `DYNASTYGM_SHOW_DEV_DESTINATIONS` | local only | `DEV_ONLY` nav | No | Must be unset | No | false; managed-host locked | No DEV_ONLY pages currently registered | Yes (gate exists) |
| `DYNASTYGM_DEV_RELOAD_MODULES` | local only | `app.py` import | No | Must be unset | No | false | No hot reload | Yes |
| `PYTHON_VERSION` | Render Blueprint | runtime | No | Yes (`3.12.10`) | Use `.python-version` | Blueprint | Wrong Python is a deploy issue | Yes |
| `PORT` | Render | Streamlit / uvicorn | No | Platform | n/a | platform | Process bind | Yes |
| `RENDER` / `RENDER_SERVICE_ID` / `RENDER_EXTERNAL_URL` | Render | managed-host detection | No | Auto | Unset | unset locally | Local contract | Yes |
| `RENDER_GIT_COMMIT` / `RENDER_GIT_BRANCH` | Render | `build_identity` | No | Auto | Unset | `DYNASTYGM_BUILD` or `local` | Footer label | Yes |
| `RENDER_SERVICE_NAME` / `RENDER_DEPLOYED_AT` | Render | Founder Ops label | No | Auto | Unset | process clock | Ops snapshot | Yes |

## Diagnostic / script-only (not production product config)

These are used by measurement scripts or opt-in traces. Leave **unset** on
customer-facing Render. Missing → tracing off. Still used in repo.

`DYNASTYGM_STARTUP`, `DYNASTYGM_RUNTIME_TRACE`, `DYNASTYGM_DASHBOARD_WATERFALL`,
`DYNASTYGM_HOT_PATH`, `DYNASTYGM_ALLOW_PRODUCTION_LOAD`, `DYNASTYGM_TEST_MODE`,
`DYNASTYGM_FEEDBACK_PATH`, `DYNASTYGM_FOUNDER_OPS_HEARTBEAT_PATH`,
`DYNASTYGM_STALL_*`, `DYNASTYGM_DEPLOYED_AT`.

Sleeper/FantasyCalc use public HTTP APIs; **no API key env vars** exist in code.

There is **no** Stripe publishable key (`pk_`) reader. Checkout is server-side.

## Duplicate authorities (keep unless proven obsolete)

| Concept | Sources | Canonical | Fallback intentional? |
| --- | --- | --- | --- |
| Any listed key | env, Streamlit secrets, `local_secrets` | **env** | Yes — Render + local Windows |
| App origin | `APP_BASE_URL`, hardcoded `PRODUCTION_BASE_URL` / `LOCAL_BASE_URL` | env when set | Yes — managed never falls back to localhost |
| Premium entitlement | Supabase `account_profile.entitlement`, then user/session fallbacks, then `DYNASTYGM_PREMIUM_OVERRIDE` | profile entitlement | Yes — override is local-only and managed-host locked |
| Founder Ops | `DYNASTYGM_FOUNDER_OPS` **and** `app_metadata.founder_ops` | both required | Yes |
| Founder Labs | `DYNASTYGM_DEV_REVIEW` **and** live session **and** (`app_metadata.founder_ops` or `app_metadata.dev_review`) | both required | Yes |
| Analytics enable | process-start `os.environ` (`ENABLED`) and `config_bool` | `config_bool` at emit time; `ENABLED` for tests | Yes — do not remove |
| Build SHA | `RENDER_GIT_COMMIT` then `DYNASTYGM_BUILD` | Render Git | Yes |
| Graduated experiments | env kill switch vs `config_bool` empty=false | `graduated_kill_switch_enabled` (empty → ON) | Yes |

## Local development

1. Copy `config/secrets.example.toml` → `local_secrets/secrets.toml` (gitignored).
2. Fill Supabase anon + URL to use accounts; leave `REPLACE_ME` to work as guest.
3. Fill Stripe test keys only to exercise checkout locally.
4. Python **3.12.10** (`.python-version`). `streamlit run app.py`.
5. Do not put service-role or webhook secrets in Streamlit secrets for day-to-day UI work.

## Render dashboard — inspected topology (2026-08-25)

Founder-verified **key names only**. Never paste secret values into tickets, logs, or this file.

**`FANTASYGMLAB` (Streamlit)** — confirmed present: `APP_BASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, Stripe billing/checkout variables. Confirmed **removed**: `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_WEBHOOK_SECRET`, and the debug/startup/analytics/experimental overrides from the earlier audit. Keep those unset. Optional: `DYNASTYGM_BUILD` (Render Git SHA is preferred). Founder Ops later: `DYNASTYGM_FOUNDER_OPS` only on a tightly controlled window; still requires Supabase `app_metadata.founder_ops`. Founder Labs later: `DYNASTYGM_DEV_REVIEW` plus `docs/founder-dev-labs.md`; do not use `DYNASTYGM_SHOW_EXPERIMENTAL` as authorization.

**`fantasygmlab-stripe-webhook`** — confirmed present: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_BILLING_MODE`. Keep Streamlit-only debug flags unset.

**Marketing Render service** — **not currently deployed.** Do not create one as part of this hygiene pass. Any static marketing site remains future or external architecture.
