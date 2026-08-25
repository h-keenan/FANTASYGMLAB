# DynastyGM deployment

Production hosting is Render (`render.yaml`). Canonical contract:
[`docs/runtime-environment-contract.md`](docs/runtime-environment-contract.md).
Operator steps: [`docs/RENDER_DEPLOYMENT.md`](docs/RENDER_DEPLOYMENT.md).

## Start command

Render Streamlit service:

```text
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

Local:

```text
streamlit run app.py
```

Python is pinned to **3.12.10** (`.python-version` and `render.yaml`).

## Environment variables

Production **does** require configuration. Local guest use does not.

Managed Streamlit hosts fail closed (clear error, not a guest/dev install) if
`SUPABASE_URL` or `SUPABASE_ANON_KEY` is missing, if `APP_BASE_URL` is loopback,
or if webhook-only secrets are present on the web process.

See the runtime environment contract for the full inventory. Do not copy secrets
into this file.

## Runtime requirements

- Outbound HTTPS to Sleeper, FantasyCalc, player-image CDNs, news feeds, Supabase, and Stripe as configured.
- Working directory = repository root.
- Durable auth/entitlement/feedback in production is Supabase, not Render disk.

## Files that must not ship from a developer machine

Mutable `data/` caches, `local_secrets/`, `.streamlit/secrets.toml`, and `.env*`
are gitignored. Deploy from git, not a dirty working tree.

## Pre-launch checks

1. Confirm Render env matches the contract checklist (values in the dashboard, not in git).
2. Confirm debug/override flags are unset on customer-facing services.
3. Confirm webhook service `/health` and `/ready` (redacted) separately from Streamlit.
