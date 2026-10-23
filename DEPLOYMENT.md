# DynastyGM deployment

Production is the self-hosted Docker Compose stack (`docker-compose.yml`):
the FastAPI mobile/web API (`services.mobile_api_service`), the Stripe and
RevenueCat webhook services, the Next.js web app (`web-next/`), Redis, and a
Caddy reverse proxy. The legacy Streamlit app (`app.py`) was removed in
2026-10 (see [`docs/streamlit-removal-2026-10.md`](docs/streamlit-removal-2026-10.md)).
Canonical contract:
[`docs/runtime-environment-contract.md`](docs/runtime-environment-contract.md).
Operator steps: [`docs/RENDER_DEPLOYMENT.md`](docs/RENDER_DEPLOYMENT.md).

## Start commands

API (see `docker-compose.yml` for the exact production command):

```text
uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT
```

Webhooks: `uvicorn services.stripe_webhook_service:app` and
`uvicorn services.revenuecat_webhook_service:app`. Web app: `npm run start`
in `web-next/`.

Python is pinned to **3.12.10** (`.python-version` and `render.yaml`).

## Environment variables

Production **does** require configuration. Local guest use does not.

Managed hosts fail closed (clear error, not a guest/dev install) if
`SUPABASE_URL` or `SUPABASE_ANON_KEY` is missing, if `APP_BASE_URL` is loopback,
or if webhook-only secrets are present on the web process.

See the runtime environment contract for the full inventory. Do not copy secrets
into this file.

## Runtime requirements

- Outbound HTTPS to Sleeper, FantasyCalc, player-image CDNs, news feeds, Supabase, and Stripe as configured.
- Working directory = repository root.
- Durable auth/entitlement/feedback in production is Supabase, not Render disk.

## Files that must not ship from a developer machine

Mutable `data/` caches, `local_secrets/`, and `.env*`
are gitignored. Deploy from git, not a dirty working tree.

## Pre-launch checks

1. Confirm Render env matches the contract checklist (values in the dashboard, not in git).
2. Confirm debug/override flags are unset on customer-facing services.
3. Confirm webhook service `/health` and `/ready` (redacted) separately from the API.
