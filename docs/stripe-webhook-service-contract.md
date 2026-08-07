# Stripe Webhook Service Contract (PR #170)

Repair and verification contract for the dedicated Stripe **Test Mode** webhook
service. Live billing is not enabled.

## Final production probe status (pre-deploy)

| Check | Result |
| --- | --- |
| `GET https://fantasygm-lab-stripe-webhook.onrender.com/health` | **404** `Not Found` |
| Response header | `x-render-routing: no-server` |
| Root cause | **No Render web service is deployed under this hostname.** This is not a missing FastAPI route. The Streamlit app exists; the webhook Blueprint service was never created/synced. |

After this PR merges, founder must **create/apply** the webhook service from `render.yaml` (or manually with the same start command). Then re-run:

```bash
python scripts/stripe_webhook_harness.py --base-url https://fantasygm-lab-stripe-webhook.onrender.com
```

Success: `/health` → 200 `{"status":"ok"}`; unsigned `POST /stripe/webhook` → **4xx** (not 404).

## Topology

| Item | Value |
| --- | --- |
| Framework | FastAPI |
| Module | `services/stripe_webhook_service.py` |
| ASGI app | `services.stripe_webhook_service:app` |
| Render service name | `fantasygm-lab-stripe-webhook` |
| Start command | `uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` (not Streamlit `/`) |
| Expected hostname | `https://fantasygm-lab-stripe-webhook.onrender.com` |
| Webhook URL | `https://fantasygm-lab-stripe-webhook.onrender.com/stripe/webhook` |
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
| `STRIPE_SECRET_KEY` | yes | Must start with `sk_test_` — `sk_live_` rejected |
| `STRIPE_WEBHOOK_SECRET` | yes | Must start with `whsec_` |
| `SUPABASE_URL` | yes | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | **Webhook only** |

### Streamlit service

| Name | Required | Notes |
| --- | --- | --- |
| `SUPABASE_SERVICE_ROLE_KEY` | **NO** | Must be absent |
| `STRIPE_SECRET_KEY` | for checkout | `sk_test_` only |
| `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_ANNUAL` | for checkout | test price ids |
| Return URL vars | recommended | success/cancel/portal |
| `DYNASTYGM_WEBHOOK_HEALTH_URL` | optional | defaults to expected `/health` URL in Founder Ops |

## Test / live safety

| Rule | Behavior |
| --- | --- |
| Secret key | Only `sk_test_…` accepted for processing |
| Live secret | `sk_live_…` → HTTP 503 on webhook; `/ready` reports `live_stripe_secret_rejected` |
| Webhook secret | Must be `whsec_…` |
| Event `livemode: true` | Rejected with BillingConfigurationError → HTTP 400 |
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

1. Supabase PATCH of the same entitlement/customer fields is naturally idempotent.
2. Process-local cache of Stripe `event.id` (6h TTL) skips a second PATCH on duplicate delivery after a successful process.
3. Harness asserts duplicate delivery does not increase PATCH count.

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

Founder Ops probes `DYNASTYGM_WEBHOOK_HEALTH_URL` or the default expected `/health` URL and shows:

- Stripe mode (`test` / missing)
- webhook reachable / health probe string
- last webhook heartbeat (if recorded)

No secrets are displayed.

## Manual steps after merge (founder)

1. Render → Blueprint Sync / create web service `fantasygm-lab-stripe-webhook` from `render.yaml`.
2. Set webhook env vars (test secrets + service role). Confirm Streamlit lacks service-role.
3. Deploy; confirm logs show uvicorn listening.
4. `python scripts/stripe_webhook_harness.py --base-url https://fantasygm-lab-stripe-webhook.onrender.com`
5. Stripe Dashboard (Test Mode) → endpoint URL `/stripe/webhook` + events from `docs/STRIPE_TEST_MODE_SETUP.md`.
6. Proceed to Test Mode lifecycle (monthly/annual/portal/cancel) — next ops gate, not this PR.

## Rollback

Revert the merge commit on `main`. If the Render webhook service was newly created, suspend/delete it in Render if needed. No Supabase schema changes in this PR.
