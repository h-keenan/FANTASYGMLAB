# Founder Beta Operational Dashboard & Health

| Field | Value |
| --- | --- |
| Baseline | `015ac26a234fb0b052df1652e1df342f25ced525` |
| Scope | Founder-only operational visibility — no football, rankings, valuations, Trust, recommendations, auth, entitlements, Stripe business logic, or Sleeper behavior changes |
| Date | 2026-08-05 |

## Access control

| Gate | Behavior |
| --- | --- |
| `DYNASTYGM_FOUNDER_OPS=1` | Required to show **Founder Ops** destination and render dashboard |
| Default (unset) | Destination absent from nav / GM Orb; `?page=founder_ops` falls back to a customer route |
| Managed Render hosts | Founder Ops flag is **independent** of `DYNASTYGM_ALLOW_PROD_DEBUG` so founders can enable ops without unlocking customer debug panels |

## Surfaces

Read-only health cards: build SHA, deploy timestamp, environment, performance budget status, cache status, startup timing, feedback counts, analytics event counts, Stripe status/health probe, last Sleeper refresh age, Supabase connection status.

Warnings: feedback backlog, webhook health failures, analytics off, cache degradation, stale public-player / Sleeper caches, Supabase session errors, startup failure flag.

Utilities: open feedback entry, analytics summary, performance summary, verify environment / Stripe / Supabase, refresh snapshot, return to Dashboard. **No destructive actions.**

## Founder enablement

```bash
# local
export DYNASTYGM_FOUNDER_OPS=1
# optional webhook probe
export DYNASTYGM_WEBHOOK_HEALTH_URL=https://<webhook-host>/health
```

On Render Streamlit: set `DYNASTYGM_FOUNDER_OPS=1` for the founder service or temporary diagnostics window, then unset when finished.

## Rollback boundary

Revert this merge commit on `main`.
