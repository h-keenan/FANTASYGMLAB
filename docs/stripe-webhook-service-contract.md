> Current authority: [webhook operations](webhook-operational-authority.md). Historical guessed-host 404 observations below do not describe the current live service. Blueprint association must be verified before any sync; do not create a duplicate.

# Stripe Webhook Service Contract (PR #170)

Repair and verification contract for the dedicated Stripe webhook service.
Test mode is the safe default. Live processing requires an explicit
`STRIPE_BILLING_MODE=live` setting and matching live credentials.

## Historical production probe status (not current authority)

Re-confirmed **2026-08-18** during Founder Beta launch-ops closure (unchanged root cause):

| Check | Result |
| --- | --- |
<!-- HISTORICAL EVIDENCE: old guessed host; not the current Render service. -->
| `GET https://fantasygm-lab-stripe-webhook.onrender.com/health` | **404** `Not Found` |
| Response header | `x-render-routing: no-server` |
| Root cause | **No Render web service is deployed under this hostname.** This is not a missing FastAPI route. The Streamlit app exists; the webhook Blueprint service was never created/synced. |
| Local code | `GET /health` → 200; unsigned `POST /stripe/webhook` → 400 (missing signature) |

Current verification: inspect the existing live service; do not create/apply the unresolved Blueprint. Run a fresh probe:

```bash
python scripts/stripe_webhook_harness.py --base-url https://fantasygmlab-stripe-webhook.onrender.com
```

Success: `/health` → 200 `{"status":"ok"}`; unsigned `POST /stripe/webhook` → **4xx** (not 404).

## Topology

| Item | Value |
| --- | --- |
| Framework | FastAPI |
| Module | `services/stripe_webhook_service.py` |
| ASGI app | `services.stripe_webhook_service:app` |
| Render service name | `fantasygmlab-stripe-webhook` |
| Start command | `uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` (not Streamlit `/`) |
| Expected hostname | `https://fantasygmlab-stripe-webhook.onrender.com` |
| Webhook URL | `https://fantasygmlab-stripe-webhook.onrender.com/stripe/webhook` |
| Auto-deploy | `branch: main` in `render.yaml` |

### Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Service identity (no secrets) |
| GET | `/health` | Liveness — always cheap; no Stripe/Supabase dependency |
| GET | `/ready` | Test-mode config readiness (issue names only) |
| POST | `/stripe/webhook` | Signed Stripe Test Mode events |

## Environment variable checklist (names only)

### Webhook service (required)

| Name | Required | Notes |
| --- | --- | --- |
| `STRIPE_BILLING_MODE` | yes | `test` or `live`; defaults to `test` when absent |
| `STRIPE_SECRET_KEY` | yes | Must match the configured mode (`sk_test_` or `sk_live_`) |
| `STRIPE_WEBHOOK_SECRET` | yes | Must start with `whsec_` |
| `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_ANNUAL` | live mode | Events may grant Premium only for these configured prices |
| `SUPABASE_URL` | yes | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | **Webhook only** |

### Streamlit service

| Name | Required | Notes |
| --- | --- | --- |
| `SUPABASE_SERVICE_ROLE_KEY` | **NO** | Must be absent |
| `STRIPE_BILLING_MODE` | yes | Must match the webhook service mode |
| `STRIPE_SECRET_KEY` | for checkout | Must match the configured mode |
| `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_ANNUAL` | for checkout | Price ids from the configured Stripe mode |
| Return URL vars | recommended | success/cancel/portal |
| `DYNASTYGM_WEBHOOK_HEALTH_URL` | optional | requires explicit public `/health` URL; missing reports `not_configured` |

## Test / live safety

| Rule | Behavior |
| --- | --- |
| Default | Missing mode resolves to `test`; a live key then fails closed |
| Secret key | Prefix must match explicit `STRIPE_BILLING_MODE` |
| Webhook secret | Must be `whsec_…` |
| Event mode | `event.livemode` must match configured mode or the event is rejected |
| No silent live fallback | Config loader does not substitute live keys |

## Entitlement event coverage (unchanged semantics)

Handled in `modules/stripe_billing.py`:

- Active → Premium: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `invoice.payment_succeeded`
- Free: `customer.subscription.deleted`, canceled/unpaid/incomplete_expired, `invoice.payment_failed`
- Cancel-at-period-end while active: remains Premium (reason annotated)
- `past_due` alone: no automatic downgrade
- Unknown events: HTTP 200 skipped no-op when no entitlement mapping

User id comes from Stripe metadata (`supabase_user_id` / client_reference_id) — never from client request body.

## Idempotency

1. Supabase stores the latest verified Stripe event id and creation time.
2. The PATCH applies only when no prior event exists or the incoming event is newer,
   so delayed replay cannot overwrite a later cancellation after restart.
3. For distinct events in the same Stripe-created second, revocation may apply but
   a grant may not. This preserves a valid revocation and prevents ambiguous paid
   access from being resurrected. Stripe event ids are identity, not ordering.
4. Process-local cache of Stripe `event.id` (6h TTL) avoids redundant requests.
5. Harness asserts duplicate delivery does not increase PATCH count.

## Supabase write boundary

- Only the webhook service loads `SUPABASE_SERVICE_ROLE_KEY`.
- Updates `profiles` via REST PATCH filtered by `user_id=eq.<metadata user>`.
- Failures return safe messages (no stack traces to Stripe).

## Local harness

```bash
# In-process ASGI contract (no network, no live Stripe)
python scripts/stripe_webhook_harness.py

# Against a running local server
uvicorn services.stripe_webhook_service:app --host 127.0.0.1 --port 8787
python scripts/stripe_webhook_harness.py --base-url http://127.0.0.1:8787

# Optional Stripe CLI (Test Mode secrets required on the local process)
stripe listen --forward-to localhost:8787/stripe/webhook
stripe trigger customer.subscription.updated
```

## Founder Ops

Founder Ops probes `DYNASTYGM_WEBHOOK_HEALTH_URL` (required; no default hostname) and shows:

- Stripe mode (`test` / missing)
- webhook reachable / health probe string
- last webhook heartbeat (if recorded)

No secrets are displayed.

## Manual steps after merge (founder)

Verify the existing `fantasygmlab-stripe-webhook` service; do not create or sync a replacement from the unresolved Blueprint. See [current webhook operations](webhook-operational-authority.md).
2. Set webhook env vars (test secrets + service role). Confirm Streamlit lacks service-role.
3. Deploy; confirm logs show uvicorn listening.
4. `python scripts/stripe_webhook_harness.py --base-url https://fantasygmlab-stripe-webhook.onrender.com`
5. Stripe Dashboard (Test Mode) → endpoint URL `/stripe/webhook` + events from `docs/STRIPE_TEST_MODE_SETUP.md`.
6. Proceed to Test Mode lifecycle (monthly/annual/portal/cancel) — next ops gate, not this PR.

## Rollback

Revert the merge commit on `main`. If the Render webhook service was newly created, suspend/delete it in Render if needed. No Supabase schema changes in this PR.
