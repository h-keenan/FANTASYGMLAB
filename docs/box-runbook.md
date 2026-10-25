# Production box runbook

What runs, how deploys work, and what to do when one is stuck. No secrets here.

## What runs

`docker compose ps` should show only:

- `mobile-api` (FastAPI, `services/mobile_api_service.py`)
- `web-next` (Next.js)
- `redis`
- `caddy` (reverse proxy)

Billing does **not** run on the box. Stripe and RevenueCat webhooks, checkout,
the billing portal and plans are Supabase Edge Functions
(`supabase/functions/`, see `docs/billing-on-supabase.md`). The old
`stripe-webhook` / `revenuecat-webhook` containers were retired in #1530.

## How a deploy works

1. A merge to `main` is picked up by the autopull timer (`fgl-release poll`).
2. The new revision is built as a **preview** and health-checked.
3. **Code-only** changes are promoted automatically.
4. Changes to Caddy, Compose, Supabase config or billing code are **blocked
   for review**. State is under `/var/lib/fantasygmlab/releases/`
   (`auto-promotion-blocked.json`).

Check where things stand:

```
fgl-release status
curl -s https://api.fantasygmlab.com/health   # "build" = live SHA
git ls-remote origin main                     # newest main SHA
```

If the `build` SHA is not the newest `main` SHA a few minutes after a merge,
the box is behind. Run `fgl-release status` and look for a blocked revision.

## Approving a blocked release

Read the diff first (what changed in `Caddyfile`, `docker-compose.yml`,
`supabase/`). If it needs a manual SQL migration, apply it in the Supabase SQL
Editor **before** promoting; promotion does not run or roll back migrations.

```
sudo /usr/local/sbin/fgl-release promote <sha> --schema-reviewed
```

Then confirm `/health` shows that SHA.

## Rolling back

```
sudo /usr/local/sbin/fgl-release rollback
```

Restores the previous release. It cannot undo database migrations.

## Host-local config: `docker-compose.override.yml`

Lives on the box, not in the repo. After editing it, always run
`docker compose config` and confirm it parses **before** promoting; a broken
override fails `docker compose ps` and can fail the deploy. Do not paste its
contents anywhere without redacting values (it holds service keys).

- Caddy's `depends_on` should list `mobile-api` and `web-next`, each
  `condition: service_healthy`. There is no `web` service any more.

## Common problems

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Analytics or a new feature missing, `/health` SHA is old | Release gate blocked | `fgl-release status`, review, promote |
| `docker compose ps` errors | Bad `docker-compose.override.yml` | `docker compose config`, fix the key it names |
| `/health` 403 from a script | Cloudflare blocking the client | Use a normal browser/curl user agent from a trusted network |
| Purchase succeeded but paywall shows | Webhook did not write `profiles` | Check Stripe events, `billing_webhook_events`, then the `profiles` row |

## Secrets

Never print or paste env files, tokens or keys. If a key is exposed, rotate
it and update both the Supabase function secret and the box.
